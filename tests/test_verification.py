from datetime import date
from backend.schemas import Candidate
from backend.verification import verify, registration_status, merge_evidence

URL = 'https://example.edu.cn/notice/2026'


def candidate(**overrides):
    return Candidate(**({'name': '测试竞赛', 'source_urls': [URL], 'evidence': [{'field': 'name', 'quote': '测试竞赛', 'source_url': URL}]} | overrides))


def test_requires_real_visited_page_and_name_quote():
    assert verify(candidate(), {}, {}) is None
    assert verify(candidate(), {URL: {'text': '无此赛事'}}, {}) is None


def test_unproven_fields_are_removed():
    result = verify(candidate(edition='2026', registration_deadline='2026-12-01', organizer='虚构单位'), {URL: {'text': '测试竞赛', 'title': '测试通知', 'captured_at': '2026-01-01'}}, {})
    assert result['name'] == '测试竞赛'
    assert result['registration_deadline'] is None
    assert result['organizer'] is None
    assert result['registration_status'] == '待核实'


def test_expired_notice_cannot_be_open():
    assert registration_status({'registration_start':'2024-01-01','registration_deadline':'2024-12-31','edition':'2024'}, date(2026,10,18)) == '已结束'


def test_unknown_start_and_edition_do_not_imply_open():
    assert registration_status({'registration_deadline':'2026-12-31','edition':'2026'}, date(2026,10,18)) == '待核实'
    assert registration_status({'registration_start':'2026-01-01','registration_deadline':'2026-12-31'}, date(2026,10,18)) == '待核实'


def test_open_upcoming_end_and_invalid_interval():
    data = {'registration_start':'2026-10-01','registration_deadline':'2026-10-18','edition':'2026年'}
    assert registration_status(data, date(2026,10,18)) == '报名中'
    assert registration_status(data, date(2026,9,18)) == '即将开始'
    assert registration_status(data, date(2026,10,19)) == '已结束'
    data['registration_start'] = '2026-11-01'
    assert registration_status(data, date(2026,10,18)) == '待核实'


def test_dates_need_exact_source_text():
    c = candidate(registration_deadline='2026-10-31', evidence=[{'field':'name','quote':'测试竞赛','source_url':URL},{'field':'registration_deadline','quote':'报名截止时间为2026年10月31日','source_url':URL}])
    pages={URL:{'text':'测试竞赛，报名截止时间为2026年10月31日。','title':'通知','captured_at':'2026-10-01'}}
    assert verify(c,pages,{})['registration_deadline'] == '2026-10-31'
    pages[URL]['text']='测试竞赛，报名截止时间待定。'
    assert verify(c,pages,{})['registration_deadline'] is None


def test_eligibility_and_conflicts_are_preserved():
    c = candidate(eligible_grades='大三及以上',evidence=[{'field':'name','quote':'测试竞赛','source_url':URL},{'field':'eligible_grades','quote':'大三及以上','source_url':URL}])
    result=verify(c,{URL:{'text':'测试竞赛，大三及以上','title':'通知','captured_at':'2026-01-01'}},{'grade':'大一'})
    assert result['eligibility_match']=='不符合'
    result['registration_deadline']='2026-12-01'
    changed={**result,'registration_deadline':'2026-12-02'}
    merged=merge_evidence(result,changed)
    assert merged['conflicts'] and merged['registration_status']=='待核实'


def test_different_editions_not_merged():
    pages={URL:{'text':'测试竞赛 2025 2026','title':'通知','captured_at':'2026-01-01'}}
    def with_year(year):
        return verify(candidate(edition=year,evidence=[{'field':'name','quote':'测试竞赛','source_url':URL},{'field':'edition','quote':year,'source_url':URL}]),pages,{})
    assert with_year('2025')['id']!=with_year('2026')['id']


def test_repeated_save_does_not_duplicate_evidence():
    result = verify(candidate(), {URL: {'text': '测试竞赛', 'title': '通知', 'captured_at': '2026-01-01'}}, {})
    merged = merge_evidence(result, result)
    assert merged['evidence'] == result['evidence']
    assert not merged['conflicts']
