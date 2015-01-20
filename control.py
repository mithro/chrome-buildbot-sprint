
import getpass
import subprocess


DISK_DEVICE_NAME_SRC = 'chromium-src'
DISK_DEVICE_NAME_OUT = 'chromium-out'


def CreateDiskFromSnapshot(disk_name, snapshot_name):
  subprocess.call(['gcloud', 'compute', 'disks', 'create', disk_name,
                   '--source-snapshot', snapshot_name])

def SnapshotDisk(disk_name, snapshot_name):
  subprocess.call(['gcloud', 'compute', 'disks', 'snapshot', disk_name,
                   '--snapshot-names', snapshot_name])

def DeleteDisk(disk_name):
  subprocess.call(['gcloud', 'compute', 'disks', 'delete', disk_name,
                   '--quiet'])

def DeleteSnapshot(snapshot_name):
  subprocess.call(['gcloud', 'compute', 'snapshots', 'delete', snapshot_name,
                   '--quiet'])


def CreateInstanceWithDisks(instance_name, image_name, src_disk=None, out_disk=None):
  params = ['gcloud', 'compute', 'instances', 'create', instance_name,
            '--image', image_name]
  if (src_disk):
    params += ['--disk', 'name=' + src_disk, 'device-name=' + DISK_DEVICE_NAME_SRC]
  if (out_disk:
    params += ['--disk', 'name=' + out_disk, 'device-name=' + DISK_DEVICE_NAME_OUT]
  subprocess.call(params)


def RunCommandOnInstance(instance_name, command):
  subprocess.call(['gcloud', 'compute', 'ssh', instance_name,
                   '--command', command])


def MountChromiumDisks(instance_name, has_src, has_out):
  if (has_src):
    chromium_dir = DISK_DEVICE_NAME_SRC
    RunCommandOnInstance(instance_name,
                         ('mkdir -p ' + chromium_dir + ';' +
                          'sudo mount /dev/disk/by-id/google-' + DISK_DEVICE_NAME_SRC + ' ' + chromium_dir + ';' +
                          'sudo chmod a+rw ' + chromium_dir + ';'))
  if (has_out):
    out_dir = DISK_DEVICE_NAME_OUT + '/src/out'
    RunCommandOnInstance(instance_name,
                         ('mkdir -p ' + out_dir + ';' +
                          'sudo mount /dev/disk/by-id/google-' + DISK_DEVICE_NAME_OUT + ' ' + out_dir + ';' +
                          'sudo chmod a+rw ' + out_dir + ';'))


def UnmountChromiumDisks(instance_name, has_src, has_out):
  if (has_out):
    RunCommandOnInstance(instance_name, 'sudo umount /dev/disk/by-id/google-' + DISK_DEVICE_NAME_OUT)
  if (has_src):
    RunCommandOnInstance(instance_name, 'sudo umount /dev/disk/by-id/google-' + DISK_DEVICE_NAME_SRC)


def DeleteInstance(instance_name):
  subprocess.call(['gcloud', 'compute', 'instances', 'delete', instance_name,
                   '--quiet'])


def NoDash(string):
  return string.replace('-', '_')

def DiskName(stage, commit, build_platform):
  return '-'.join([NoDash(getpass.getuser()), 'disk', NoDash(build_platform), NoDash(commit), stage])

def InstanceName(stage, commit, build_platform):
  return '-'.join([NoDash(getpass.getuser()), 'instance', NoDash(build_platform), NoDash(commit), stage])

def SnapshotName(stage, commit, build_platform):
  return '-'.join([NoDash(getpass.getuser()), 'snapshot', NoDash(build_platform), NoDash(commit), stage])

def ImageName():
  return 'ubuntu-14-04'

def UpdateAndBuild(target_stage, target_commit, from_commit, build_platform):
  if target_stage == 'src':
    src_disk_name = DiskName('src', target_commit, build_platform)
    CreateDiskFromSnapshot(src_disk_name, SnapshotName('src', from_commit, build_platform))
    instance_name = InstanceName('src', target_commit, build_platform)
    CreateInstanceWithDisks(instance_name, ImageName(), src_disk=src_disk_name)
    MountChromiumDisks(instance_name, True, False)
    RunCommandOnInstance(instance_name, 'ls chromium')
    RunCommandOnInstance(instance_name, 'touch chromium/something')
    UnmountChromiumDisks(instance_name, True, False)
    SnapshotDisk(src_disk_name, SnapshotName('src', target_commit, build_platform))
    DeleteInstance(instance_name)
    # Don't delete disk, 'build' stage will use it read-only.

  if target_stage == 'build':
    src_disk_name = DiskName('src', target_commit, build_platform)
    out_disk_name = DiskName('build', target_commit, build_platform)
    CreateDiskFromSnapshot(out_disk_name, SnapshotName('build', target_commit, build_platform))
    instance_name = InstanceName('build', target_commit, build_platform)
    CreateInstanceWithDisks(instance_name, ImageName(), src_disk=src_disk_name, out_disk=out_disk_name)
    MountChromiumDisks(instance_name, True, True)
    RunCommandOnInstance(instance_name, 'ls chromium')
    RunCommandOnInstance(instance_name, 'touch chromium/something')
    UnmountChromiumDisks(instance_name, True, True)
    SnapshotDisk(out_disk_name, SnapshotName('build', target_commit, build_platform))
    DeleteInstance(instance_name)
    # Don't delete disk, 'test' stage will use it read-only.

  if target_stage == 'test':
    out_disk_name = DiskName('test', target_commit, build_platform)
    instance_name = InstanceName('test', target_commit, build_platform)
    CreateInstanceWithDisks(instance_name, ImageName(), out_disk=out_disk_name)
    MountChromiumDisks(instance_name, False, True)
    RunCommandOnInstance(instance_name, 'ls chromium')
    RunCommandOnInstance(instance_name, 'touch chromium/something')
    UnmountChromiumDisks(instance_name, False, True)
    DeleteInstance(instance_name)