"""Explicit live acceptance; requires running local services and a saved key.

Usage: python -m scripts.live_acceptance EXISTING_SEARCH_TASK_ID
Calls the configured paid model. Keeps all task records and restores settings.
"""
import csv
import io
import json
import sys
import time
from pathlib import Path

import httpx


def main(task_id):
    report = {'search_task_id': task_id}
    with httpx.Client(base_url='http://127.0.0.1:8000', timeout=40) as client:
        def get_task(identifier):
            response = client.get(f'/api/tasks/{identifier}')
            response.raise_for_status()
            return response.json()['data']

        def wait_terminal(identifier, seconds=350):
            end = time.monotonic() + seconds
            while time.monotonic() < end:
                task = get_task(identifier)
                if task['status'] not in ('queued', 'running', 'cancelling'):
                    print(json.dumps({'task': identifier, 'status': task['status'], 'count': task['result_count']}), flush=True)
                    return task
                time.sleep(2)
            raise TimeoutError('Task did not finish within acceptance budget')

        search = wait_terminal(task_id)
        report['search'] = search
        for extension in ('csv', 'md'):
            response = client.get(f'/api/tasks/{task_id}/export', params={'format': extension})
            response.raise_for_status()
            Path(f'docs/live-search.{extension}').write_bytes(response.content)
            if extension == 'csv':
                rows = list(csv.DictReader(io.StringIO(response.content.decode('utf-8-sig'))))
                assert {row['name'] for row in rows} == {row['name'] for row in search['results']}
            else:
                assert all(url in response.text for row in search['results'] for url in row['source_urls'])
        stream = client.get(f'/api/tasks/{task_id}/events')
        assert 'event: end' in stream.text
        ids = [int(line[4:]) for line in stream.text.splitlines() if line.startswith('id: ')]
        assert ids == sorted(set(ids)) and len(ids) == len(search['events'])
        report['export_consistency'] = report['sse_replay'] = 'PASS'

        original = client.get('/api/settings').json()['data']
        allowed = ('llm_provider', 'model', 'api_base_url', 'max_steps', 'timeout_seconds', 'max_pages', 'default_count', 'headless')
        saved = {key: original[key] for key in allowed}
        try:
            response = client.post('/api/tasks', json={'query': '取消验收测试：寻找人工智能大学生竞赛。'})
            response.raise_for_status()
            cancel_id = response.json()['data']['id']
            deadline = time.monotonic() + 45
            while time.monotonic() < deadline:
                if any(event['type'] == 'browser_started' for event in get_task(cancel_id)['events']):
                    break
                time.sleep(1)
            else:
                raise AssertionError('Browser did not start before cancellation')
            response = client.post(f'/api/tasks/{cancel_id}/cancel')
            response.raise_for_status()
            report['cancel'] = wait_terminal(cancel_id, 40)
            assert report['cancel']['status'] == 'cancelled'
            response = client.put('/api/settings', json={**saved, 'timeout_seconds': 30})
            response.raise_for_status()
            response = client.post('/api/tasks', json={'query': '超时验收测试：搜索并核对全国八项人工智能大学生赛事的本届报名日期和参赛要求，逐项打开原始通知并保存证据。'})
            response.raise_for_status()
            timeout_id = response.json()['data']['id']
            report['timeout'] = wait_terminal(timeout_id, 70)
            assert report['timeout']['status'] in ('failed', 'partial')
            assert '超时' in report['timeout']['error']
            assert client.get('/api/health').json()['data']['active_tasks'] == 0
            report['lifecycle'] = 'PASS'
        finally:
            response = client.put('/api/settings', json=saved)
            report['settings_restored'] = response.status_code == 200
            Path('docs/live-acceptance.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
        assert report['settings_restored']
        print('Exports, SSE replay, real browser cancellation, timeout, and settings restoration: PASS', flush=True)


if __name__ == '__main__':
    main(sys.argv[1])
