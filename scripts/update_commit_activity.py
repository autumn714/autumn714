"""Update commit time/weekday charts from public, owned default-branch history.

Uses the authenticated gh CLI (GH_TOKEN in Actions). No WakaTime account is
required. Only aggregate counts are saved; commit messages and emails are not.
"""
import argparse
import json
import subprocess
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import quote, urlencode

ROOT = Path(__file__).resolve().parents[1]
KST = timezone(timedelta(hours=9), 'Asia/Seoul')
PERIODS = [('Morning', '06:00–11:59'), ('Daytime', '12:00–17:59'),
           ('Evening', '18:00–23:59'), ('Night', '00:00–05:59')]
DAYS = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']
START = '<!-- COMMIT_ACTIVITY:START -->'
END = '<!-- COMMIT_ACTIVITY:END -->'

def api_pages(gh, endpoint, empty_repository=False):
    result = subprocess.run([gh, 'api', '--paginate', '--slurp', endpoint],
                            capture_output=True, text=True, encoding='utf-8')
    if result.returncode:
        if empty_repository and 'Git Repository is empty' in result.stdout + result.stderr:
            return []
        raise RuntimeError(f'GitHub API request failed: {endpoint} (exit {result.returncode})')
    pages = json.loads(result.stdout)
    if not isinstance(pages, list) or any(not isinstance(page, list) for page in pages):
        raise ValueError(f'Unexpected API response shape: {endpoint}')
    return [item for page in pages for item in page]

def collect_commits(gh, username):
    repos = api_pages(gh, f'/users/{quote(username, safe="")}/repos?type=owner&per_page=100')
    public_owned = [repo for repo in repos if not repo.get('private')
                    and repo.get('owner', {}).get('login', '').lower() == username.lower()]
    records = []
    for repo in sorted(public_owned, key=lambda item: item['name'].lower()):
        endpoint = '/repos/' + '/'.join(quote(part, safe='') for part in repo['full_name'].split('/'))
        query = urlencode({'author':username, 'sha':repo['default_branch'], 'per_page':100})
        commits = api_pages(gh, endpoint + '/commits?' + query, empty_repository=True)
        for commit in commits:
            author = commit.get('author') or {}
            if author.get('type') == 'Bot':
                continue
            date = commit['commit']['author']['date']
            records.append({'sha':commit['sha'], 'date':date})
    return records, len(public_owned)

def aggregate(records):
    periods = [0] * 4
    weekdays = [0] * 7
    seen = set()
    dates = []
    for record in records:
        if record['sha'] in seen:
            continue
        seen.add(record['sha'])
        stamp = datetime.fromisoformat(record['date'].replace('Z','+00:00'))
        if stamp.utcoffset() is None:
            raise ValueError('Commit timestamps must include a timezone')
        local = stamp.astimezone(KST)
        hour = local.hour
        bucket = 0 if 6 <= hour < 12 else 1 if 12 <= hour < 18 else 2 if hour >= 18 else 3
        periods[bucket] += 1
        weekdays[local.weekday()] += 1
        dates.append(local.date())
    return {'total':len(seen), 'time_of_day':periods, 'weekdays':weekdays,
            'first_commit_date':str(min(dates)) if dates else None,
            'last_commit_date':str(max(dates)) if dates else None}

def chart(labels, counts, total):
    lines = []
    for label, count in zip(labels, counts):
        percent = count / total * 100 if total else 0
        filled = round(count / total * 25) if total else 0
        bar = '█' * filled + '░' * (25-filled)
        lines.append(f'{label:<10} {count:>5} commits  {bar} {percent:>6.2f} %')
    return '\n'.join(lines)

def render(summary):
    day_chart = chart(DAYS, summary['weekdays'], summary['total'])
    period_chart = chart([item[0] for item in PERIODS], summary['time_of_day'], summary['total'])
    return f'''{START}
**🕒 Commits by Time of Day**

```text
{period_chart}
```

**📅 Commits by Day of Week**

```text
{day_chart}
```

<sub>Public commits · KST (UTC+9) · {summary['total']} commits · Updated {summary['updated_on']}</sub>

<details>
<summary>집계 기준</summary>

- 본인 소유 공개 저장소의 기본 브랜치에서 {summary['username']} 작성자로 조회되는 커밋을 집계합니다.
- 커밋 작성 시각을 한국 시간으로 변환하며, 같은 SHA는 한 번만 셉니다.
- Morning 06–12시 · Daytime 12–18시 · Evening 18–24시 · Night 00–06시입니다.
- 위 Streak 카드에는 다른 저장소의 활동 등도 포함될 수 있어 두 통계의 총합은 다를 수 있습니다.

</details>
{END}'''

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--gh', default='gh')
    parser.add_argument('--username', default='autumn714')
    args = parser.parse_args()
    records, repository_count = collect_commits(args.gh, args.username)
    summary = aggregate(records)
    summary.update({'username':args.username, 'timezone':'Asia/Seoul',
                    'repository_count':repository_count,
                    'updated_on':str(datetime.now(KST).date()),
                    'scope':'Owned public repositories; default branches; author date; unique SHA'})
    readme_path = ROOT / 'README.md'
    readme = readme_path.read_text(encoding='utf-8')
    if readme.count(START) != 1 or readme.count(END) != 1:
        raise ValueError('README must have one commit activity marker pair')
    begin, end_marker = readme.index(START), readme.index(END)
    if begin >= end_marker:
        raise ValueError('Invalid commit activity marker order')
    end = end_marker + len(END)
    output = readme[:begin] + render(summary) + readme[end:]
    data_path = ROOT / 'profile' / 'commit-activity.json'
    data_path.write_text(json.dumps(summary, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')
    readme_path.write_text(output, encoding='utf-8')
    print(f'Updated {summary["total"]} unique commits across {repository_count} public repositories (KST).')

if __name__ == '__main__':
    main()
