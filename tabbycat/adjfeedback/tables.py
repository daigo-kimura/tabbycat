import logging

from utils.misc import reverse_tournament
from utils.tables import TabbycatTableBuilder

from .progress import FeedbackProgressForAdjudicator, FeedbackProgressForTeam

logger = logging.getLogger(__name__)


class FeedbackTableBuilder(TabbycatTableBuilder):

    def add_breaking_checkbox(self, adjudicators, key="Breaking"):
        breaking_header = {
            'key': 'B',
            'icon': 'award',
            'tooltip': 'Whether the adj is marked as breaking (click to mark)',
        }
        breaking_data = [{
            'component': 'check-cell',
            'checked':  adj.breaking ,
            'sort': adj.breaking,
            'type': 'breaking',
            'saveURL': reverse_tournament('adjfeedback-set-adj-breaking-status', self.tournament),
            'id': adj.pk,
        } for adj in adjudicators]

        self.add_column(breaking_header, breaking_data)

    def add_weighted_score_columns(self, adjudicators):
        feedback_weight = self.tournament.current_round.feedback_weight
        score_func = self.tournament.avg_feedback_score_func
        scores = {adj: adj.weighted_score(feedback_weight, score_func) for adj in adjudicators}

        overall_header = {
            'key': 'Score',
            'text': 'Score',
            'tooltip': 'Current weighted score',
        }
        overall_data = [{
            'sort': scores[adj],
            'text': '<strong>%0.1f</strong>' % scores[adj] if scores[adj] is not None else 'N/A',
            'tooltip': 'This adjudicator\'s current rating.',
        } for adj in adjudicators]
        self.add_column(overall_header, overall_data)

    def add_test_score_columns(self, adjudicators, editable=False):
        test_header = {
            'key': 'Test Score',
            'icon': 'clipboard',
            'tooltip': 'Test score result',
        }
        if editable:
            test_data = [{
                'text': '%0.1f' % adj.test_score if adj.test_score is not None else 'N/A',
                'modal': adj.id,
                'class': 'edit-test-score',
                'tooltip': 'Click to edit test score',
            } for adj in adjudicators]
        else:
            test_data = [{
                'text': '%0.1f' % adj.test_score if adj.test_score is not None else 'N/A',
                'tooltip': 'Assigned test score',
            } for adj in adjudicators]

        self.add_column(test_header, test_data)

    def add_feedback_graphs(self, adjudicators):
        feedback_head = {
            'key': 'Feedback',
            'text': 'Feedback',
            'tooltip': 'Hover over the data points to show the average score received in that round'
        }
        feedback_graph_data = [{
            'graphData': adj.feedback_data,
            'component': 'feedback-trend',
            'minScore': self.tournament.pref('adj_min_score'),
            'maxScore': self.tournament.pref('adj_max_score'),
            'roundSeq': len(self.tournament.prelim_rounds()),
        } for adj in adjudicators]
        self.add_column(feedback_head, feedback_graph_data)

    def add_feedback_link_columns(self, adjudicators):
        link_head = {
            'key': 'VF',
            'icon': 'zoom-in'
        }
        link_cell = [{
            'text': 'View<br>Feedback',
            'class': 'view-feedback',
            'link': reverse_tournament('adjfeedback-view-on-adjudicator', self.tournament, kwargs={'pk': adj.pk})
        } for adj in adjudicators]
        self.add_column(link_head, link_cell)

    def add_feedback_misc_columns(self, adjudicators):
        if self.tournament.pref('enable_adj_notes'):
            note_head = {
                'key': 'NO',
                'icon': 'tablet'
            }
            note_cell = [{
                'text': 'Edit<br>Note',
                'class': 'edit-note',
                'modal': str(adj.id) + '===' + str(adj.notes)
            } for adj in adjudicators]
            self.add_column(note_head, note_cell)

        adjudications_head = {
            'key': 'DD',
            'icon': 'eye',
            'tooltip': 'Debates adjudicated'
        }
        adjudications_cell = [{'text': adj.debates} for adj in adjudicators]
        self.add_column(adjudications_head, adjudications_cell)

        avgs_head = {
            'key': 'AVGS',
            'icon': 'crosshair',
            'tooltip': 'Average Margin (top) and Average Score (bottom)'
        }
        avgs_cell = [{
            'text': "%0.1f<br>%0.1f" % (adj.avg_margin if adj.avg_margin else 0, adj.avg_score if adj.avg_margin else 0),
            'tooltip': 'Average Margin (top) and Average Score (bottom)'
        } for adj in adjudicators]
        self.add_column(avgs_head, avgs_cell)

    def add_feedback_progress_columns(self, progress_list, key="P"):

        def _owed_cell(progress):
            owed = progress.num_unsubmitted()
            cell = {
                'text': owed,
                'sort': owed,
                'class': 'text-danger strong' if owed > 0 else 'text-success'
            }
            return cell

        owed_header = {
            'key': 'Owed',
            'icon': 'slash',
            'tooltip': 'Unsubmitted feedback ballots',
        }
        owed_data = [_owed_cell(progress) for progress in progress_list]
        self.add_column(owed_header, owed_data)

        if self._show_record_links:

            def _record_link(progress):
                if isinstance(progress, FeedbackProgressForTeam):
                    url_name = 'participants-team-record' if self.admin else 'participants-public-team-record'
                    pk = progress.team.pk
                elif isinstance(progress, FeedbackProgressForAdjudicator):
                    url_name = 'participants-adjudicator-record' if self.admin else 'participants-public-adjudicator-record'
                    pk = progress.adjudicator.pk
                else:
                    logger.error("Unrecognised progress type: %s", progress.__class__.__name__)
                    return ''
                return reverse_tournament(url_name, self.tournament, kwargs={'pk': pk})

            owed_link_header = {
                'key': 'Submitted',
                'icon': 'check',
            }
            owed_link_data = [{
                'text': 'View Missing Feedback',
                'link': _record_link(progress)
            } for progress in progress_list]
            self.add_column(owed_link_header, owed_link_data)
