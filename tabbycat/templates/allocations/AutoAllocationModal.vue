<template>
  <div class="modal fade" id="confirmAutoAllocationModal" tabindex="-1" role="dialog" aria-hidden="true">
    <div class="modal-dialog">
      <div class="modal-content">
        <div class="modal-body">
          <p class="lead">Using auto-allocate will <strong>remove all existing adjudicator
          allocations</strong> and create new panels for all debates.</p>
          <p>The allocator forms stronger panels for debates that have been assigned higher
          importances. If importances have not been set, or are equivalent, it will give
          stronger panels to debates in a higher bracket.</p>
          <p>Adjudicators must have a feedback score over <strong>{{ roundInfo.scoreForVote }}</strong>
          to panel. You can change this in the <em>Draw Rules</em> section of Configuration if needed.
          Try modifying this value if you are seeing too few or too many panellists being allocated.</p>
          <div v-if="roundInfo.scoreForVote > roundInfo.scoreMax" class="alert alert-warning">
            The score required to panel ({{ roundInfo.scoreForVote }}) is higher than the maximum
            adjudicator score ({{ roundInfo.scoreMax }}). You should probably lower the score required
            to panel in settings.
          </div>
          <div v-if="roundInfo.scoreForVote < roundInfo.scoreMin" class="alert alert-warning">
            The score required to panel ({{ roundInfo.scoreForVote }}) is lower than the minimum
            adjudicator score ({{ roundInfo.scoreMin }}). You should probably raise the score
            required to panel in settings.
          </div>
          <button type="submit" class="btn btn-block btn-success"
                  @click="createAutoAllocation">
            Create Automatic Allocation
          </button>
        </div>
      </div>
    </div>
  </div>
</template>

<script>
export default {
  props: { roundInfo: Object, },
  methods: {
    resetAutoAllocationModal: function(button) {
      $('#confirmAutoAllocationModal').modal('hide')
      $.fn.resetButton(button)
    },
    createAutoAllocation: function(event) {
      var self = this
      $.fn.loadButton(event.target)
      $.post({
        url: this.roundInfo.autoUrl,
        dataType: 'json',
      }).done(function(data, textStatus, jqXHR) {
        // Success handler
        self.$eventHub.$emit('update-allocation', JSON.parse(data.debates))
        self.$eventHub.$emit('update-unallocated', JSON.parse(data.unallocatedAdjudicators))
        self.$eventHub.$emit('update-saved-counter', this.updateLastSaved)
        self.resetAutoAllocationModal(event.target)
        $.fn.showAlert('success', 'Successfully loaded the auto allocation', 10000)
      }).fail(function(response) {
        // Handle Failure
        console.debug(JSON.stringify(response)) // Help identify failures in sentry
        var info = response.responseJSON.message
        $.fn.showAlert('danger', 'Auto Allocation failed: ' + info, 0)
        self.resetAutoAllocationModal(event.target)
      })
    },
  }
}

</script>
