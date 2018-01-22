from django.test import TestCase

from utils.tests import ConditionalTableViewTestsMixin
from participants.models import Adjudicator, Speaker


class PublicParticipantsViewTestCase(ConditionalTableViewTestsMixin, TestCase):

    view_toggle = 'public_features__public_participants'
    view_name = 'participants-public-list'

    def table_data_a(self):
        # Check number of adjs matches
        return Adjudicator.objects.filter(tournament=self.t).count()

    def table_data_b(self):
        # Check number of speakers matches
        return Speaker.objects.filter(team__tournament=self.t).count()
