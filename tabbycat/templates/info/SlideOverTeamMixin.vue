<script>
// Mainly just handles formatting the object for the slideover
import SlideOverDiversityMixin from './SlideOverDiversityMixin.vue'
import _ from 'lodash'

export default {
  data: function () {
    return { annotationMethodName: 'addConflictsAnnotation' }
  },
  mixins: [SlideOverDiversityMixin],
  computed: {
    breakCategoriesFeature: function() {
      var self = this
      if (this.roundInfo.teamsInDebate === 'bp') {
        var resultsInfo = [{ 'title': 'On ' + self.team.points + ' points' }]
      } else {
        var resultsInfo = [{ 'title': 'On ' + self.team.wins + ' wins' }]
      }
      var bcInfo = _.map(this.team.break_categories, function(bc) {
        return {
          'title': self.titleForBC(bc),
          'class': 'category-display category-' + bc.class,
          'icon': self.iconForBC(bc)
        }
      })
      return resultsInfo.concat(bcInfo)
    },
    teamInfoFeature: function() {
      var self = this
      var teamInfo = { 'title': this.team.short_name }
      var speakersInfo = _.map(this.team.speakers, function(s) {
        return {
          'title': s.name + " " + self.genderBrackets(s.gender),
          'class': 'gender-display gender-' + s.gender,
          'icon': 'user'
        }
      })
      return _.concat(teamInfo, speakersInfo)
    },
    annotateDataForSlideOver: function() {
      return this.team
    }
  },
  methods: {
    titleForBC: function(bc, wins) {
      if (!_.isUndefined(bc.will_break)) {
        if (bc.will_break !== null) {
          return bc.will_break.toUpperCase() + ' for ' + bc.name + ' Break'
        } else {
          return bc.name + ' Break'
        }
      }
    },
    iconForBC: function(bc) {
      if (bc.will_break === 'dead') { return 'x' } else
      if (bc.will_break === 'safe') { return 'check' } else
      if (bc.will_break === 'live') { return 'star' }
      else { return '' }
    },
    formatForSlideOver: function(subject) {
      return {
        'tiers': [{
          'features': [
            this.teamInfoFeature,
            this.institutionDetailForSlideOver(this.team),
            this.breakCategoriesFeature,
          ]
        }]
      }
    },
  }
}
</script>
