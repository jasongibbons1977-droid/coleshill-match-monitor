import unittest
from datetime import datetime
from copy import deepcopy
from monitor import chunks, drafts, fixtures, match, parse_time, goal_graphic, graphic_markdown, brand_drafts, matchday_opener, LONDON


class MonitorTests(unittest.TestCase):
    def test_matchday_opener_before_lineups_and_no_repeat(self):
        data = {'teams': {'home': {'name': 'Wellingborough Town', 'score': None}, 'away': {'name': 'Coleshill Town', 'score': None}}, 'events': []}
        now = datetime(2026, 10, 24, 14, 20, tzinfo=LONDON)
        text = matchday_opener(data, '15:00:00', now, {})
        self.assertEqual(len(text), 1)
        self.assertIn('Kick-off: 3pm UK', text[0])
        self.assertIn('@PackMeadow', text[0])
        self.assertLessEqual(len(text[0]), 270)
        self.assertEqual(matchday_opener(data, '15:00:00', now, {'matchday': True}), [])
        self.assertEqual(matchday_opener(data, '15:00:00', now.replace(hour=16), {}), [])

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

    def test_coleshill_scorer_has_correct_graphic(self):
        data = self.sample()
        data['lineups']['home'] = ['Bassit Mandey']
        text = "⚽ 12' Bassit Mandey scores\nLatest score: Coleshill Town 1-0 Visitors"
        self.assertEqual(goal_graphic(text, data)['path'], 'graphics/bassit-mandey.jpg')
        self.assertIn('raw.githubusercontent.com/owner/repo/main/graphics/bassit-mandey.jpg', graphic_markdown(text, data, 'owner/repo'))

    def test_opposition_scorer_does_not_get_our_graphic(self):
        data = self.sample()
        data['lineups']['away'] = ['Bassit Mandey']
        self.assertIsNone(goal_graphic("⚽ 12' Bassit Mandey scores", data))

    def test_own_goals_and_unknown_scorers_do_not_get_graphics(self):
        data = self.sample()
        data['lineups']['home'] = ['Bassit Mandey', 'New Player']
        self.assertIsNone(goal_graphic("⚽ 12' Bassit Mandey scores an own goal", data))
        self.assertIsNone(goal_graphic("⚽ 12' New Player scores", data))

    def test_known_full_name_alias_and_captain_suffix(self):
        data = self.sample()
        data['lineups']['home'] = ['Benjamin Usher-Shipway (C)']
        self.assertEqual(goal_graphic("⚽ 12' Benjamin Usher-Shipway scores", data)['player'], 'Ben Usher-Shipway')

    def test_away_coleshill_scorer(self):
        data = self.sample()
        data['teams']['home']['name'] = 'Visitors'
        data['teams']['away']['name'] = 'Coleshill Town'
        data['lineups']['away'] = ['Daniel Gyasi']
        self.assertEqual(goal_graphic("⚽ 90+2' Daniel Gyasi scores", data)['path'], 'graphics/daniel-gyasi.jpg')

    def test_every_draft_has_pack_meadow_branding(self):
        texts, _ = drafts(self.sample(), {})
        self.assertTrue(texts)
        for text in texts:
            self.assertIn('Live At Pack Meadow | @PackMeadow', text)
            self.assertNotIn('facebook.com', text)
            self.assertEqual(text.count('#ColeshillTown'), 1)
            self.assertLessEqual(len(text), 270)

    def test_long_draft_keeps_information_and_branding(self):
        words = ['Player' + str(i) for i in range(70)]
        result = brand_drafts([' '.join(words) + '\n#ColeshillTown'])
        self.assertGreater(len(result), 1)
        for word in words:
            self.assertIn(word, '\n'.join(result))
        self.assertTrue(all(len(text) <= 270 for text in result))

    def test_goal_tone_and_graphics_survive_branding(self):
        data = self.sample()
        data['lineups']['home'] = ['Bassit Mandey']
        data['lineups']['away'] = ['Away Scorer']
        data['events'] = ["12'Bassit Mandey scores", "20'Away Scorer scores"]
        texts, _ = drafts(data, {})
        ours = next(t for t in texts if 'Bassit Mandey scores' in t)
        theirs = next(t for t in texts if 'Away Scorer scores' in t)
        self.assertIn('GOAL, COLESHILL!', ours)
        self.assertIn('Goal for Visitors', theirs)
        self.assertNotIn('GOAL, COLESHILL!', theirs)
        self.assertEqual(goal_graphic(ours, data)['player'], 'Bassit Mandey')


if __name__ == '__main__':
    unittest.main()
