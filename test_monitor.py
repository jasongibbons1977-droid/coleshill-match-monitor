import unittest
from copy import deepcopy
from monitor import chunks, drafts, fixtures, match, parse_time


class MonitorTests(unittest.TestCase):
    def sample(self):
        return {'teams': {'home': {'name': 'Coleshill Town', 'score': '2'},
                          'away': {'name': 'Visitors', 'score': '1'}},
                'lineups': {'home': ['Player ' + str(i) for i in range(1, 17)], 'away': []},
                'events': ["Full-time: Coleshill Town 2-1 Visitors", "Half-time: Coleshill Town 1-0 Visitors",
                           "12'Player 3 scores", "70'Player 12 replaced Player 3"]}

    def test_repeat_has_no_drafts(self):
        data = self.sample()
        first, snapshot = drafts(data, {})
        self.assertGreater(len(first), 3)
        self.assertEqual(drafts(data, snapshot)[0], [])

    def test_updated_score_not_false_historical_goal_score(self):
        data = self.sample()
        texts, _ = drafts(data, {})
        goal = next(t for t in texts if 'scores' in t)
        self.assertIn('Latest score: Coleshill Town 2-1 Visitors', goal)
        self.assertIn("12' Player 3", goal)
        self.assertTrue(all(len(t) <= 280 for t in texts))

    def test_no_inferred_half_or_full_time(self):
        data = self.sample()
        data['events'] = []
        texts, _ = drafts(data, {})
        self.assertFalse(any('Full-time' in t or 'Half-time' in t for t in texts))

    def test_correction(self):
        data = self.sample()
        _, snapshot = drafts(data, {})
        data['events'] = data['events'][:-1]
        self.assertTrue(any('corrected' in t for t in drafts(data, snapshot)[0]))

    def test_partial_xi_not_announced(self):
        data = self.sample()
        data['lineups']['home'] = ['A', 'B']
        self.assertFalse(any('TEAM NEWS' in t for t in drafts(data, {})[0]))

    def test_chunks_preserve_all_names(self):
        names = ['A very long footballer name ' + str(i) for i in range(20)]
        texts = chunks('Starting XI: ', names)
        self.assertTrue(all(len(t) <= 280 for t in texts))
        for name in names:
            self.assertIn(name, '\n'.join(texts))

    def test_explicit_times(self):
        self.assertEqual(str(parse_time('7.45pm')), '19:45:00')
        self.assertEqual(str(parse_time('3pm')), '15:00:00')
        self.assertIsNone(parse_time('P-P'))

    def test_base_url_not_team_relative(self):
        html = '<table><tr data-href="match/cup/example/123" title="Home v Away"><td class="date" data-export="27/10/2026">Tue 27 Oct</td><td class="ko-score">7.45pm</td></tr></table>'
        row = fixtures(html)[0]
        self.assertEqual(row['url'], 'https://www.footballwebpages.co.uk/match/cup/example/123')
        self.assertEqual(row['time'], '19:45:00')

    def test_reject_missing_or_wrong_match(self):
        with self.assertRaises(ValueError):
            match('<html>Server error</html>')


if __name__ == '__main__':
    unittest.main()
