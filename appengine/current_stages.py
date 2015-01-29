import helpers
import objects
import stages

# Earliest commit comes first
COMMIT_LIST = (
  'fa1651193bf94120',
  '32cbfaa6478f66b9',
  '1874cd207f996341',
  '863dc8b59882bf44',
)

def get_current_stages():
  base_commit = COMMIT_LIST[0]
  base_snapshot_name = helpers.SnapshotName(base_commit, "src")
  assert objects.Snapshot.load(base_snapshot_name).ready(), '%s must exist' % base_snapshot_name

  previous_commit = base_commit
  current_stages = []
  for current_commit in COMMIT_LIST[1:]:
    current_stages.append(stages.SyncStage(previous_commit, current_commit))
    previous_commit = current_commit
  return current_stages
