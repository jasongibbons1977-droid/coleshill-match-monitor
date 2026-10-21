"""Standard-library-only Coleshill Town match monitor. Never publishes to X."""
import argparse
import hashlib
import json
import os
import re
import unicodedata
from datetime import datetime, timedelta, time
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import quote, urljoin, urlparse
from urllib.request import Request, urlopen
from zoneinfo import ZoneInfo

BASE = 'https://www.footballwebpages.co.uk/'
FIXTURES = BASE + 'coleshill-town/fixtures-results'
LONDON = ZoneInfo('Europe/London')
STATE = Path('state.json')
BRANDING = 'Live At Pack Meadow | @PackMeadow\n#ColeshillTown'


def brand_drafts(texts):
    """Include Pack Meadow X branding in every draft without dropping content."""
    limit = 270 - len(BRANDING) - 2
    result = []
    for text in texts:
        body = text.replace('\n#ColeshillTown', '').strip()
        while len(body) > limit:
            cut = body.rfind(' ', 0, limit + 1)
            if cut < 1:
                cut = limit
            result.append(body[:cut].strip() + '\n\n' + BRANDING)
            body = body[cut:].strip()
        if body:
            result.append(body + '\n\n' + BRANDING)
    return result


class Node:
    def __init__(self, tag='', attrs=()):
        self.tag, self.attrs, self.children = tag, dict(attrs), []

    def has(self, cls):
        return cls in self.attrs.get('class', '').split()

    def find(self, tag=None, cls=None):
        result = []
        for child in self.children:
            if isinstance(child, Node):
                if (tag is None or child.tag == tag) and (cls is None or child.has(cls)):
                    result.append(child)
                result.extend(child.find(tag, cls))
        return result

    def text(self):
        return re.sub(r'\s+', ' ', ''.join(c.text() if isinstance(c, Node) else c for c in self.children)).strip()


class Document(HTMLParser):
    def __init__(self, html):
        super().__init__(convert_charrefs=True)
        self.root = Node()
        self.stack = [self.root]
        self.feed(html)

    def handle_starttag(self, tag, attrs):
        n = Node(tag, attrs)
        self.stack[-1].children.append(n)
        if tag == 'br':
            n.children.append(' ')
        if tag not in {'area', 'base', 'br', 'col', 'embed', 'hr', 'img', 'input', 'link', 'meta', 'param', 'source', 'track', 'wbr'}:
            self.stack.append(n)

    def handle_endtag(self, tag):
        for i in range(len(self.stack) - 1, 0, -1):
            if self.stack[i].tag == tag:
                self.stack = self.stack[:i]
                break

    def handle_data(self, data):
        self.stack[-1].children.append(data)


def get(url):
    if urlparse(url).hostname != 'www.footballwebpages.co.uk':
        raise ValueError('Unexpected source host')
    req = Request(url, headers={'User-Agent': 'ColeshillMatchMonitor/1.0 (public match updates; five-minute checks)'})
    with urlopen(req, timeout=30) as response:
        if urlparse(response.url).hostname != 'www.footballwebpages.co.uk':
            raise ValueError('Unexpected source redirect')
        return response.read(2_000_000).decode('utf-8')


def parse_time(text):
    m = re.fullmatch(r'(\d{1,2})(?:[:.](\d{2}))?\s*(am|pm)', text.strip().lower())
    if not m:
        return None
    hour, minute, ampm = m.groups()
    return time(int(hour) % 12 + (12 if ampm == 'pm' else 0), int(minute or 0))


def fixtures(html):
    rows = []
    for row in Document(html).root.find('tr'):
        path = row.attrs.get('data-href', '')
        dates, scores = row.find('td', 'date'), row.find('td', 'ko-score')
        if not path.startswith('match/') or not dates or not scores:
            continue
        date = datetime.strptime(dates[0].attrs['data-export'], '%d/%m/%Y').date()
        ko = parse_time(scores[0].text())
        rows.append({'id': path.rsplit('/', 1)[-1], 'date': date.isoformat(),
                     'time': ko.isoformat() if ko else None, 'url': urljoin(BASE, path),
                     'title': row.attrs.get('title', 'Coleshill Town match'),
                     'listing': scores[0].text()})
    if not rows:
        raise ValueError('No fixture rows found; source format may have changed')
    return rows


def match(html):
    root = Document(html).root
    summary = root.find('ul', 'match-summary')
    if not summary:
        raise ValueError('Match summary missing; refusing to invent updates')
    teams, goals, lineups = {}, {}, {}
    for side in ['home', 'away']:
        team = summary[0].find('li', side + '-team')
        if not team or not team[0].find('h4'):
            raise ValueError('Team name missing')
        heading = team[0].find('h4')[0]
        spans = heading.find('span')
        score = spans[0].text() if spans else None
        name = ''.join(x.text() if isinstance(x, Node) and x.tag != 'span' else x if isinstance(x, str) else '' for x in heading.children).strip()
        teams[side] = {'name': name, 'score': score}
        # Summary goal entries identify the credited team, including own goals.
        goals[side] = team[0].find('p')[0].text() if team[0].find('p') else ''
        box = root.find('div', side + '-line-up')
        names = []
        if box:
            for li in box[0].find('li'):
                player = li.find('span', 'player')
                if player:
                    names.append(player[0].text())
        lineups[side] = names
    if 'Coleshill Town' not in [x['name'] for x in teams.values()]:
        raise ValueError('Not a Coleshill Town match')
    events = []
    for ul in root.find('ul', 'match-events'):
        for li in ul.find('li'):
            if li.text():
                events.append(li.text())
    return {'teams': teams, 'lineups': lineups, 'events': events}


def chunks(prefix, names):
    result, current = [], prefix
    for name in names:
        add = ('' if current == prefix or current.endswith('\n') else ', ') + name
        if len(current + add) > 270 - len(BRANDING) - 2:
            result.append(current + '\n#ColeshillTown')
            current = 'Team news continued: ' + name
        else:
            current += add
    if current != prefix:
        result.append(current + '\n#ColeshillTown')
    return result


def drafts(data, previous):
    output = []
    home, away = data['teams']['home'], data['teams']['away']
    score = None
    if home['score'] is not None and away['score'] is not None:
        score = f"{home['name']} {home['score']}-{away['score']} {away['name']}"
    side = 'home' if home['name'] == 'Coleshill Town' else 'away'
    names = data['lineups'][side]
    old_names = previous.get('lineup', [])
    # Wait for a full XI. FWP lists starters first, then substitutes.
    if len(names) >= 11 and names != old_names:
        title = 'LINE-UP UPDATE' if old_names else 'TEAM NEWS'
        opponent = away['name'] if side == 'home' else home['name']
        output.extend(chunks(f'{title} | Coleshill Town v {opponent}\nStarting XI: ', names[:11]))
        if len(names) > 11:
            output.extend(chunks('Coleshill Town substitutes:\n', names[11:]))
    seen = set(previous.get('events', []))
    new_events = [event for event in data['events'] if event not in seen]
    # Timed events first, then explicit HT/FT confirmations. Never infer either from the clock.
    timed = [e for e in new_events if re.match(r"^\d+(?:\+\d+)?'", e)]
    phases = sorted([e for e in new_events if e not in timed],
                    key=lambda e: 2 if re.search('full.time', e, re.I) else 1 if re.search('half.time', e, re.I) else 0)
    for event in timed + phases:
        if not re.search(r'scores|replaced|cautioned|sent off|dismissed|half.time|full.time|kick.off|postponed|abandoned|penalt', event, re.I):
            continue
        event = re.sub(r"^(\d+(?:\+\d+)?')(?=\S)", r'\1 ', event)
        text = event
        goal = re.match(r"^(\d+(?:\+\d+)?')\s+(.+?)\s+scores\b", event)
        if goal:
            scorer = normalize_player(goal.group(2))
            our_players = {normalize_player(n) for n in data['lineups'][side]}
            other_side = 'away' if side == 'home' else 'home'
            their_players = {normalize_player(n) for n in data['lineups'][other_side]}
            if 'own goal' in event.lower():
                heading = '⚽ OWN GOAL UPDATE'
            elif scorer in our_players:
                heading = '⚽ GOAL, COLESHILL!'
            elif scorer in their_players:
                heading = '⚽ Goal for ' + data['teams'][other_side]['name']
            else:
                heading = '⚽ GOAL UPDATE'
            text = heading + '\n' + event.rstrip('.') + '.'
        elif re.match('half.time:', event, re.I):
            text = 'HALF-TIME | ' + event.split(':', 1)[1].strip()
        elif re.match('full.time:', event, re.I):
            text = 'FULL-TIME | ' + event.split(':', 1)[1].strip()
        elif ' replaced ' in event:
            text = '🔄 SUBSTITUTION\n' + event.rstrip('.') + '.'
        elif re.search('cautioned|sent off|dismissed', event, re.I):
            text = 'MATCH UPDATE\n' + event.rstrip('.') + '.'
        if score and re.search('scores|replaced|cautioned|sent off|dismissed', event, re.I):
            text += '\nLatest score: ' + score
        text += '\n#ColeshillTown'
        if len(text) <= 280:
            output.append(text)
    if score and score != previous.get('score') and not timed and not phases:
        output.append('SCORE UPDATE | ' + score + '\n#ColeshillTown')
    # Source corrections are explicit rather than silently leaving inaccurate tweets unflagged.
    removed = seen - set(data['events'])
    if removed:
        text = 'UPDATE | The match feed has corrected earlier information.'
        if score:
            text += '\nLatest score: ' + score
        output.append(text + '\n#ColeshillTown')
    return brand_drafts(output), {'events': data['events'], 'lineup': names, 'score': score}


def github(method, path, body=None):
    token = os.environ['GH_TOKEN']
    req = Request('https://api.github.com/' + path, method=method,
                  data=json.dumps(body).encode() if body is not None else None,
                  headers={'Authorization': 'Bearer ' + token, 'Accept': 'application/vnd.github+json',
                           'X-GitHub-Api-Version': '2022-11-28', 'Content-Type': 'application/json'})
    with urlopen(req, timeout=30) as response:
        return json.load(response)


def normalize_player(name):
    name = re.sub(r'\s*\(C\)\s*$', '', name, flags=re.I)
    return ' '.join(re.sub(r'[^a-z0-9]+', ' ', unicodedata.normalize('NFKD', name).encode('ascii', 'ignore').decode().lower()).split())


def goal_graphic(text, data):
    """Return an exact-matched graphic only for a Coleshill scorer, never an own goal."""
    scorer = re.search(r"(?:^⚽\s+|^)(?:\d+(?:\+\d+)?')\s+(.+?)\s+scores\b", text, re.I | re.M)
    if not scorer or 'own goal' in text.lower():
        return None
    name = normalize_player(scorer.group(1))
    side = next((s for s, team in data['teams'].items() if team['name'] == 'Coleshill Town'), None)
    roster = {normalize_player(n) for n in data['lineups'].get(side, [])}
    if not side or name not in roster:
        return None
    manifest = Path(__file__).parent / 'graphics' / 'players.json'
    if not manifest.exists():
        return None
    for player, asset in json.loads(manifest.read_text()).items():
        if name in {normalize_player(n) for n in [player] + asset.get('aliases', [])}:
            path = asset['file']
            if not path.startswith('graphics/') or '..' in path.split('/') or not (manifest.parent.parent / path).is_file():
                return None
            return {'player': player, 'path': path}
    return None


def graphic_markdown(text, data, repo):
    asset = goal_graphic(text, data)
    if not asset:
        return ''
    url = f"https://raw.githubusercontent.com/{repo}/main/{asset['path']}"
    return ('\n\n### Goal graphic — ' + asset['player'] + '\n\n'
            '![' + asset['player'] + ' goal graphic](' + url + ')\n\n'
            '[**Open full-size graphic**](' + url + ')\n\n'
            'On iPhone: open the graphic, touch and hold it, then save it to Photos. '
            'Use **Open in X** above and attach the saved graphic before posting.')


def deliver(fixture, texts, saved, data):
    repo, owner = os.environ['GITHUB_REPOSITORY'], os.environ['GITHUB_REPOSITORY_OWNER']
    if not saved.get('issue'):
        # Recover an existing match issue after a failed state commit.
        existing = github('GET', f'repos/{repo}/issues?state=all&per_page=100')
        marker = '<!-- match:' + fixture['id'] + ' -->'
        found = next((i for i in existing if marker in (i.get('body') or '')), None)
        issue = found or github('POST', f'repos/{repo}/issues', {
            'title': fixture['date'] + ' | ' + fixture['title'], 'assignees': [owner],
            'body': marker + '\n\nMatch updates and X drafts for @' + owner + '.\n\n'
                    'Tap **Open in X**, review the draft and tap Post. Nothing is published automatically.\n\n'
                    '[Match source](' + fixture['url'] + ')\n\n'
                    'Checks are about five minutes apart and may be delayed. Source updates may also arrive late.'})
        saved['issue'] = issue['number']
    path = f"repos/{repo}/issues/{saved['issue']}/comments"
    comments, page = [], 1
    while True:
        batch = github('GET', path + f'?per_page=100&page={page}')
        comments.extend(batch)
        if len(batch) < 100:
            break
        page += 1
    bodies = '\n'.join(c.get('body', '') for c in comments)
    for text in texts:
        digest = hashlib.sha256(text.encode()).hexdigest()[:24]
        marker = '<!-- draft:' + digest + ' -->'
        if marker in bodies:
            continue
        url = 'https://twitter.com/intent/tweet?text=' + quote(text, safe='')
        github('POST', path, {'body': marker + '\n\n@' + owner + ' — new match draft:\n\n'
               + text + '\n\n[**Open in X**](' + url + ') · [Check source](' + fixture['url'] + ')'
               + graphic_markdown(text, data, repo)})


def run(now, dry_run=False):
    state = json.loads(STATE.read_text()) if STATE.exists() else {'matches': {}}
    state.setdefault('matches', {})
    # Saturdays use the user's fixed window; midweek windows follow the fixture kick-off.
    if now.weekday() == 6 or (now.weekday() == 5 and not time(14) <= now.time().replace(tzinfo=None) <= time(17, 30)):
        print('Outside requested monitoring window')
        return
    today = now.date().isoformat()
    cached = state.get('fixtures', {})
    age = (now - datetime.fromisoformat(cached['at'])).total_seconds() if cached.get('at') else float('inf')
    if age >= 3600 or cached.get('date') != today:
        state['fixtures'] = {'at': now.isoformat(), 'date': today, 'rows': fixtures(get(FIXTURES))}
    count = 0
    for fixture in state['fixtures']['rows']:
        if fixture['date'] != today:
            continue
        saved = state['matches'].setdefault(fixture['id'], {})
        kickoff = fixture.get('time') or saved.get('kickoff')
        if kickoff:
            saved['kickoff'] = kickoff
        if now.weekday() != 5:
            # If first seen after kick-off, the listing may already show a score.
            # In that case check the match page once to obtain its explicit kick-off.
            if not kickoff:
                html = get(fixture['url'])
                m = re.search(r'Kick-off:\s*([^<]+)', html)
                parsed = parse_time(m.group(1)) if m else None
                kickoff = parsed.isoformat() if parsed else None
                if kickoff:
                    saved['kickoff'] = kickoff
            if not kickoff:
                print('No confirmed kick-off for', fixture['id'])
                continue
            ko = datetime.combine(now.date(), time.fromisoformat(kickoff), LONDON)
            if not ko - timedelta(hours=1) <= now <= ko + timedelta(hours=2, minutes=30):
                continue
        data = match(get(fixture['url']))
        if re.search(r'\b(?:P-P|postponed)\b', fixture.get('listing', ''), re.I):
            data['events'].append('Postponed: ' + fixture['title'])
        texts, snapshot = drafts(data, saved)
        if texts:
            if dry_run:
                print(json.dumps(texts, ensure_ascii=False, indent=2))
            else:
                deliver(fixture, texts, saved, data)
            count += len(texts)
        saved.update(snapshot)
    if not dry_run:
        STATE.write_text(json.dumps(state, ensure_ascii=False, indent=2) + '\n')
    print(f'{count} new drafts')


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--dry-run', action='store_true')
    parser.add_argument('--check-source', action='store_true')
    args = parser.parse_args()
    if args.check_source:
        rows = fixtures(get(FIXTURES))
        today = datetime.now(LONDON).date().isoformat()
        future = [r for r in rows if r['date'] >= today]
        past = [r for r in rows if r['date'] < today]
        for row in (future[:1] + past[-1:]):
            data = match(get(row['url']))
            print('Source OK:', row['date'], row['title'], '|', len(data['events']), 'events;',
                  len(data['lineups']['home']), 'home players;', len(data['lineups']['away']), 'away players')
        print('Fixture rows:', len(rows))
    else:
        run(datetime.now(LONDON), args.dry_run)
