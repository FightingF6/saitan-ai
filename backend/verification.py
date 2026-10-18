import hashlib
import re
from datetime import date, datetime
from zoneinfo import ZoneInfo
from urllib.parse import urlsplit
from .db import now
from .schemas import Candidate


def local_today():
    return datetime.now(ZoneInfo('Asia/Shanghai')).date()


def compact(value):
    return re.sub(r'\s+', '', str(value)).lower()


def date_in_text(value: date, text: str):
    patterns = (value.isoformat(), f'{value.year}年{value.month}月{value.day}日', f'{value.year}/{value.month}/{value.day}', f'{value.year}.{value.month}.{value.day}')
    normalized = re.sub(r'(?<=[年/月.\-])0(?=\d)', '', compact(text))
    return any(re.sub(r'(?<=[年/月.\-])0(?=\d)', '', p) in normalized for p in patterns)


def registration_status(data: dict, today: date | None = None):
    today = today or local_today()
    start, end = data.get('registration_start'), data.get('registration_deadline')
    if data.get('conflicts') or not end:
        return '待核实'
    end = date.fromisoformat(end)
    if end < today:
        return '已结束'
    if not start or not data.get('edition') or str(today.year) not in data['edition']:
        return '待核实'
    start = date.fromisoformat(start)
    if start > end:
        return '待核实'
    return '即将开始' if start > today else '报名中'


def verify(candidate: Candidate, pages: dict, filters: dict):
    """Accept only literal, field-specific evidence from browser-captured pages.

    This proves text presence, not site authority or the semantic truth of claims.
    """
    valid_sources = [str(url) for url in candidate.source_urls if str(url) in pages]
    if not valid_sources:
        return None
    proofs = {}
    for evidence in candidate.evidence:
        url = str(evidence.source_url)
        if url in valid_sources and compact(evidence.quote) in compact(pages[url]['text']):
            proofs.setdefault(evidence.field, []).append(evidence)
    data = candidate.model_dump(mode='json', exclude={'evidence'})
    supported = []
    for field, value in list(data.items()):
        if field in ('source_urls', 'official_url') or value is None:
            continue
        witnesses = proofs.get(field, [])
        matched = [e for e in witnesses if (date_in_text(date.fromisoformat(value), e.quote) if field in ('registration_start', 'registration_deadline', 'source_published_at') else compact(value) in compact(e.quote))]
        if not matched:
            data[field] = None
        else:
            supported.extend(e.model_dump(mode='json') for e in matched)
    if not data['name']:
        return None
    data['official_url'] = None  # An agent's claim alone cannot establish official ownership.
    data['source_urls'] = valid_sources
    data['sources'] = [{'url': url, 'title': pages[url]['title'], 'captured_at': pages[url]['captured_at'], 'source_type': '高校公告' if urlsplit(url).hostname.endswith('.edu.cn') else '网页来源', 'verification_status': '原文已比对', 'excerpt': '\n'.join(e['quote'] for e in supported if e['source_url'] == url)[:4000]} for url in valid_sources]
    data['evidence'] = supported
    data['conflicts'] = []
    if data['registration_start'] and data['registration_deadline'] and data['registration_start'] > data['registration_deadline']:
        data['conflicts'].append('报名开始时间晚于截止时间')
    data['registration_status'] = registration_status(data)
    data['verification_status'] = '已核实原文' if data['registration_status'] != '待核实' else '待核实'
    data['last_verified_at'] = now()
    grade = filters.get('grade', '')
    eligibility = data.get('eligible_grades') or ''
    excluded = bool(grade in ('大一', '大二') and ('大三及以上' in eligibility or '仅限研究生' in eligibility))
    data['eligibility_match'] = '不符合' if excluded else ('符合已知条件' if grade and grade in eligibility else '需确认参赛条件')
    matches = [v for k in ('category', 'major') if (v := filters.get(k)) and v in (data.get('category') or '') + (data.get('eligible_majors') or '')]
    data['match_count'] = len(matches)
    data['recommendation_reason'] = '参赛年级与当前条件不符，作为资料保留。' if excluded else (f'原文包含与你需求相关的「{"、".join(matches)}」。' if matches else '已找到赛事原文，请结合参赛条件确认适用性。')
    identity = '|'.join((compact(data['name']), compact(data['edition'] or ''), urlsplit(valid_sources[0]).netloc if data['edition'] else valid_sources[0]))
    data['id'] = hashlib.sha256(identity.encode()).hexdigest()[:32]
    return data


def merge_evidence(previous, current):
    conflicts = list(previous.get('conflicts', []))
    for field in ('registration_start', 'registration_deadline', 'eligible_grades', 'participation_type'):
        if previous.get(field) and current.get(field) and previous[field] != current[field]:
            conflicts.append(f'{field} 来源冲突：{previous[field]} / {current[field]}')
    result = {**previous, **{k: v for k, v in current.items() if v is not None}}
    result['source_urls'] = list(dict.fromkeys(previous['source_urls'] + current['source_urls']))
    result['sources'] = list({s['url']: s for s in previous['sources'] + current['sources']}.values())
    result['evidence'] = list({(e['field'], compact(e['quote']), e['source_url']): e for e in previous['evidence'] + current['evidence']}.values())
    result['conflicts'] = list(dict.fromkeys(conflicts))
    result['registration_status'] = registration_status(result)
    if conflicts:
        result['verification_status'] = '待核实'
    return result
