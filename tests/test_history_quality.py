import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from test_content_recovery import b


class HistoryQualityTests(unittest.TestCase):
    def test_vacated_camp_cannot_portray_active_fire(self):
        scene = b.Scene(narration='Smoke rose over the Anacostia flats as makeshift shelters fed the flames.',
            visual_query='vacated camp', archive_id='a1', source_ids=[1])
        script = type('Draft', (), {'scenes': [scene]})()
        inventory = {'a1': {'item': {'tags': '[Vacated Bonus Army camp?]'}, 'visible_context': 'Camp following the eviction.'}}
        with patch.dict(b.HISTORY_MEDIA, inventory, clear=True):
            self.assertTrue(b.history_evidence_scope_issues(script))
            scene.narration = 'An emptied camp remained after the veterans were evicted from their makeshift homes.'
            self.assertEqual(b.history_evidence_scope_issues(script), [])

    def test_police_policy_label_requires_specific_actor(self):
        scene = b.Scene(narration='The superintendent favored a peaceful settlement.', visual_query='official approaches',
            diagram=b.ExplainerSpec(kind='comparison', title='Authority split',
                labels=['Police restraint', 'Military force'], note='Different approaches to the protest.'), source_ids=[1])
        script = type('Draft', (), {'scenes': [scene]})()
        self.assertTrue(b.history_evidence_scope_issues(script))
        scene.diagram.labels = ["Glassford's approach", "MacArthur's approach"]
        self.assertEqual(b.history_evidence_scope_issues(script), [])

    def test_whole_photo_remains_visible_during_motion(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / 'photo.png'
            image = b.Image.new('RGB', (900, 600), 'white')
            draw = b.ImageDraw.Draw(image)
            draw.rectangle((0, 0, 899, 599), outline='red', width=24)
            image.save(path)
            background, photo = b.archive_layers(path)
            start = b.np.array(b.archive_motion_frame(background, photo, 0))
            end = b.np.array(b.archive_motion_frame(background, photo, 1))
        self.assertEqual(start.shape, (1920, 1080, 3))
        self.assertGreater(b.np.abs(start.astype(float) - end).mean(), .1)
        # Red border survives on every side at both motion extremes.
        for frame in [start, end]:
            red = (frame[:, :, 0] > 220) & (frame[:, :, 1] < 40) & (frame[:, :, 2] < 40)
            self.assertTrue(red[450:1150, :100].any())
            self.assertTrue(red[450:1150, 980:].any())
            self.assertTrue(red[450:530].any())
            self.assertTrue(red[1050:1130].any())

    def test_comparison_has_separate_reveal_without_data_bars(self):
        spec = b.ExplainerSpec(kind='comparison', title='Different approaches',
            labels=['One approach', 'Another approach'], note='Illustrative comparison, without numerical measurements.')
        early = b.np.array(b.explainer_frame(spec, b.CHANNELS['history'], .5, 6))
        late = b.np.array(b.explainer_frame(spec, b.CHANNELS['history'], 2, 6))
        self.assertGreater(b.np.abs(early[850:1000].astype(float) - late[850:1000]).mean(), .5)
