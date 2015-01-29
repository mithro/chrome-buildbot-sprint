import helpers
import objects
import stages

def get_current_stages():
  previous_commit = COMMIT_LIST[0]
  base_snapshot_name = helpers.SnapshotName(previous_commit, "src")
  assert objects.Snapshot.load(base_snapshot_name).ready(), '%s must exist' % base_snapshot_name

  current_stages = []
  for current_commit in COMMIT_LIST[1:]:
    current_stages.append(stages.SyncStage(previous_commit, current_commit))
    current_stages.append(stages.BuildStage(None, current_commit))
    previous_commit = current_commit
  return current_stages

COMMIT_LIST = (
  '4108ce09f9ead01f', # Wed Jan 21 00:06:33 2015 +0000
  '4220eea6d0c7ffa9', # Wed Jan 21 00:21:22 2015 +0000
  # 'a9f61f02eb555b0b', # Wed Jan 21 00:23:12 2015 +0000
  # '7f17a7758881aa33', # Wed Jan 21 00:53:21 2015 +0000
  # 'aa928ff8aa04cba9', # Wed Jan 21 00:58:34 2015 +0000
  # '045c9bf1d36f3564', # Wed Jan 21 06:05:23 2015 +0000
  # '090a00e7ff8c5fb1', # Wed Jan 21 11:05:05 2015 +0000
  # 'd6552661356cafdc', # Wed Jan 21 11:06:44 2015 +0000
  # '2935666ed30c24a2', # Wed Jan 21 11:06:45 2015 +0000
  # 'a78fa6fc306c6f49', # Wed Jan 21 11:09:09 2015 +0000
  # 'c514ed05c61d4228', # Wed Jan 21 11:09:10 2015 +0000
  # '6febb4ef7865fada', # Wed Jan 21 11:09:11 2015 +0000
  # '21b128297b19076f', # Wed Jan 21 11:10:51 2015 +0000
  # 'ae8bda577e76b4e3', # Wed Jan 21 11:10:52 2015 +0000
  # 'faf8b453fa03869b', # Wed Jan 21 11:27:16 2015 +0000
  # '6f4aa7e2069231cb', # Wed Jan 21 11:44:36 2015 +0000
  # '4359db72cde4fe4e', # Wed Jan 21 12:40:49 2015 +0000
  # '9d533c4211e366ed', # Wed Jan 21 12:42:14 2015 +0000
  # '6154ce77f15a68c8', # Wed Jan 21 12:45:58 2015 +0000
  # '281667e0bdcde1e4', # Wed Jan 21 12:45:59 2015 +0000
  # '2c5518d7b7d3eb11', # Wed Jan 21 13:13:46 2015 +0000
  # 'c497f3788bc5007e', # Wed Jan 21 13:40:30 2015 +0000
  # '275932c2d51cb9e1', # Wed Jan 21 13:46:28 2015 +0000
  # '368d94621cb29485', # Wed Jan 21 13:54:50 2015 +0000
  # 'ae1a91dab26b089c', # Wed Jan 21 13:56:15 2015 +0000
  # 'ed8d899eb98bfe38', # Wed Jan 21 13:57:49 2015 +0000
  # 'b3f95493b4dcd134', # Wed Jan 21 13:57:50 2015 +0000
  # '22a80e71d7199d9d', # Wed Jan 21 13:59:11 2015 +0000
  # '678686d7440e28b1', # Wed Jan 21 13:59:12 2015 +0000
  # 'a39cae03de3894cd', # Wed Jan 21 14:03:24 2015 +0000
  # 'f0c11866899ffd0b', # Wed Jan 21 14:03:25 2015 +0000
  # '4cf3535f639fe037', # Wed Jan 21 14:03:26 2015 +0000
  # '52f6146bdbd80b89', # Wed Jan 21 14:03:27 2015 +0000
  # '1d47a35e40040daf', # Wed Jan 21 14:03:28 2015 +0000
  # '402e5206669870c1', # Wed Jan 21 14:03:29 2015 +0000
  # '81197b2560fae7c1', # Wed Jan 21 14:05:12 2015 +0000
  # '035125910439fc66', # Wed Jan 21 14:05:13 2015 +0000
  # 'd8c057d71ae5062b', # Wed Jan 21 14:06:40 2015 +0000
  # '50f9c8e35e788b65', # Wed Jan 21 14:08:11 2015 +0000
  # 'cf03eb0c4b236143', # Wed Jan 21 14:08:12 2015 +0000
  # 'dcbf4aabe86ac33d', # Wed Jan 21 14:09:45 2015 +0000
  # 'f555fec2b8769deb', # Wed Jan 21 14:09:46 2015 +0000
  # '0eeb6a9a3b410797', # Wed Jan 21 14:11:14 2015 +0000
  # 'e0f868e9bb4f5ca5', # Wed Jan 21 14:11:15 2015 +0000
  # 'b43e6cc69ecb0049', # Wed Jan 21 14:12:36 2015 +0000
  # 'd0a0c992fc0eb9c8', # Wed Jan 21 14:14:29 2015 +0000
  # 'e0abded3fd525ff0', # Wed Jan 21 14:14:30 2015 +0000
  # 'd7e021d86cd234f8', # Wed Jan 21 14:16:07 2015 +0000
  # 'eb1f1be18cdec48c', # Wed Jan 21 14:16:08 2015 +0000
  # 'dadaac36b84938d9', # Wed Jan 21 14:17:52 2015 +0000
  # 'cbe97a623786ec36', # Wed Jan 21 14:17:53 2015 +0000
  # 'dad6da460d13947b', # Wed Jan 21 14:17:54 2015 +0000
  # '49c6e74138dc5f81', # Wed Jan 21 14:19:21 2015 +0000
  # '465662ed7e306369', # Wed Jan 21 14:20:52 2015 +0000
  # 'dcd1e0f17a992eb2', # Wed Jan 21 14:20:53 2015 +0000
  # '4b9c17e27d575055', # Wed Jan 21 14:22:21 2015 +0000
  # '183ce6363d441d4d', # Wed Jan 21 14:22:22 2015 +0000
  # 'c7971906db1f36ad', # Wed Jan 21 14:23:56 2015 +0000
  # '8a516c4f82192361', # Wed Jan 21 14:23:57 2015 +0000
  # '6d5ce7f1c3c11516', # Wed Jan 21 14:25:55 2015 +0000
  # '0a2a1898d00213dc', # Wed Jan 21 14:25:56 2015 +0000
  # '5a388d809868ec83', # Wed Jan 21 14:27:30 2015 +0000
  # '8d6edba93eabb174', # Wed Jan 21 14:27:31 2015 +0000
  # 'd892fde82106439d', # Wed Jan 21 14:28:58 2015 +0000
  # '9f83dd3a3c48f3b0', # Wed Jan 21 14:28:59 2015 +0000
  # '77abcf7d289ec445', # Wed Jan 21 14:30:31 2015 +0000
  # '956993f22a92339f', # Wed Jan 21 14:30:32 2015 +0000
  # '0dc6c55b60d7593d', # Wed Jan 21 14:32:05 2015 +0000
  # '57988d1f46e6ce2a', # Wed Jan 21 14:33:46 2015 +0000
  # 'f4bdb54c848a8152', # Wed Jan 21 14:35:58 2015 +0000
  # '351519fd09084647', # Wed Jan 21 14:35:59 2015 +0000
  # '557114ed77022971', # Wed Jan 21 14:36:00 2015 +0000
  # 'd7ce058384dd9226', # Wed Jan 21 14:38:16 2015 +0000
  # '0539f2f5214fc17f', # Wed Jan 21 14:38:17 2015 +0000
  # '05b2c7ba7ea3bd77', # Wed Jan 21 14:40:00 2015 +0000
  # 'e97add26342fadfb', # Wed Jan 21 14:40:01 2015 +0000
  # 'ef0ffb7c3d8532fa', # Wed Jan 21 14:41:44 2015 +0000
  # '24a0f3a78b2bc83f', # Wed Jan 21 14:41:45 2015 +0000
  # '8910d20fdabea7c0', # Wed Jan 21 14:41:46 2015 +0000
  # 'df59d8f077f7541b', # Wed Jan 21 14:43:14 2015 +0000
  # 'ec410fc086b7bad2', # Wed Jan 21 14:44:41 2015 +0000
  # 'a13d9af247043eaf', # Wed Jan 21 14:44:42 2015 +0000
  # 'b6624b457c5fd667', # Wed Jan 21 14:46:12 2015 +0000
  # '1a77411405391fa9', # Wed Jan 21 14:46:13 2015 +0000
  # '0d264850d7d8b983', # Wed Jan 21 14:47:42 2015 +0000
  # '9bbad24aa9990d23', # Wed Jan 21 14:47:43 2015 +0000
  # '8862ce36105a75af', # Wed Jan 21 14:49:33 2015 +0000
  # '97dc995002ed64b0', # Wed Jan 21 14:49:34 2015 +0000
  # '38a6fabc90e33b04', # Wed Jan 21 15:18:56 2015 +0000
  # 'e98e8e7654b7e51f', # Wed Jan 21 15:26:40 2015 +0000
  # 'f752426485290ebf', # Wed Jan 21 15:28:39 2015 +0000
  # '99d4c15b5ac4dd32', # Wed Jan 21 15:31:11 2015 +0000
  # 'cd3a95252fc67e46', # Wed Jan 21 15:41:11 2015 +0000
  # 'e55e9aabcb12008a', # Wed Jan 21 15:42:46 2015 +0000
  # '063efcf45e7d9ea6', # Wed Jan 21 15:56:53 2015 +0000
  # 'fb5251d1ff4f36ea', # Wed Jan 21 15:58:20 2015 +0000
  # '3f7a8d0427d48ddd', # Wed Jan 21 16:42:45 2015 +0000
  # '99273f63af064e8e', # Wed Jan 21 17:14:06 2015 +0000
  # '3df4b87b4bb419d8', # Wed Jan 21 19:51:12 2015 +0000
  # '612dc5e5e6b287ec', # Wed Jan 21 19:55:34 2015 +0000
  # '97a646ae131c24ce', # Wed Jan 21 19:57:04 2015 +0000
  # 'd733ef8b689ed772', # Wed Jan 21 19:58:36 2015 +0000
  # 'b1f519c37f766377', # Wed Jan 21 19:58:37 2015 +0000
  # 'e8043e53867a334b', # Wed Jan 21 20:00:11 2015 +0000
  # 'b2514129e3a9d696', # Wed Jan 21 20:12:51 2015 +0000
  # '7df36b27afc2da12', # Wed Jan 21 20:14:22 2015 +0000
  # '0458a61127a58dc6', # Wed Jan 21 20:16:22 2015 +0000
  # '91ff1e3964c0d2c4', # Wed Jan 21 20:16:23 2015 +0000
  # 'f714289259132eb6', # Wed Jan 21 20:16:24 2015 +0000
  # 'd4ef11808ce81d02', # Wed Jan 21 20:17:58 2015 +0000
  # '0ccd70c6f3fa1bf5', # Wed Jan 21 20:17:59 2015 +0000
  # '92da739316361e17', # Wed Jan 21 20:19:32 2015 +0000
  # '515812f023528794', # Wed Jan 21 20:19:33 2015 +0000
  # '04e509c9db0ad64e', # Wed Jan 21 20:20:57 2015 +0000
  # '950f0d49b0157ed4', # Wed Jan 21 20:22:22 2015 +0000
  # '07a8e92fb99ff032', # Wed Jan 21 20:22:23 2015 +0000
  # '3a8ce9fdae852cfa', # Wed Jan 21 20:23:49 2015 +0000
  # '4671a458da766f19', # Wed Jan 21 20:23:50 2015 +0000
  # '57b2c6c8543cc5b2', # Wed Jan 21 20:25:11 2015 +0000
  # 'c1a91a8a6a7132c4', # Wed Jan 21 20:27:17 2015 +0000
  # '9b9d2e0a172bf3c3', # Wed Jan 21 20:27:18 2015 +0000
  # 'a0a8384802be386f', # Wed Jan 21 20:28:52 2015 +0000
  # '2abacff7ad83e48d', # Wed Jan 21 20:28:53 2015 +0000
  # 'd724e7bcc7b15109', # Wed Jan 21 20:30:20 2015 +0000
  # '1bb3d1d4a9d51553', # Wed Jan 21 20:31:50 2015 +0000
  # 'ae98daac90e8a97f', # Wed Jan 21 20:31:51 2015 +0000
  # '603647627bf638b6', # Wed Jan 21 20:33:21 2015 +0000
  # '0b332db0581b1381', # Wed Jan 21 20:33:22 2015 +0000
  # '21959d33ba15f4e4', # Wed Jan 21 20:35:07 2015 +0000
  # '52cfea1ccce19c42', # Wed Jan 21 20:35:08 2015 +0000
  # '20419e404d3a7a49', # Wed Jan 21 20:36:45 2015 +0000
  # 'bd2e01dd0860762c', # Wed Jan 21 20:36:46 2015 +0000
  # 'ed24b6f85f73b2a5', # Wed Jan 21 20:39:54 2015 +0000
  # 'af7073b5633518bc', # Wed Jan 21 20:39:55 2015 +0000
  # 'afbf7f097f96b0de', # Wed Jan 21 20:39:56 2015 +0000
  # 'ceeb4976a531646f', # Wed Jan 21 20:39:57 2015 +0000
  # 'c46ccfb7031ebf01', # Wed Jan 21 20:41:45 2015 +0000
  # '1e511856ab4e7bf1', # Wed Jan 21 20:41:46 2015 +0000
  # '9e614a242c34f760', # Wed Jan 21 20:43:18 2015 +0000
  # '5ce2ee76f1512eda', # Wed Jan 21 20:43:19 2015 +0000
  # 'bdf05a13f9723f12', # Wed Jan 21 20:44:49 2015 +0000
  # '7d3d8bceeac97d0a', # Wed Jan 21 20:44:50 2015 +0000
  # 'e587c6d4dd88d910', # Wed Jan 21 20:46:23 2015 +0000
  # 'e16def6f1ddbc987', # Wed Jan 21 20:48:09 2015 +0000
  # '4f0c73e6744b9a73', # Wed Jan 21 20:48:10 2015 +0000
  # '5ea0476b1f36f667', # Wed Jan 21 20:49:45 2015 +0000
  # '2598c69a3c184095', # Wed Jan 21 20:49:46 2015 +0000
  # '075d9d1f37299ce1', # Wed Jan 21 20:51:56 2015 +0000
  # '6f5f3596aa4517f0', # Wed Jan 21 20:51:57 2015 +0000
  # 'efc9f803c794c74d', # Wed Jan 21 20:53:43 2015 +0000
  # '2dfb76d84f4ebde6', # Wed Jan 21 20:53:44 2015 +0000
  # '2b60792760a1291c', # Wed Jan 21 20:53:45 2015 +0000
  # 'df9798c024d53f22', # Wed Jan 21 21:16:57 2015 +0000
  # '4e30d62669c312dd', # Wed Jan 21 21:18:35 2015 +0000
  # 'e6867c0023bc8ba7', # Wed Jan 21 21:20:10 2015 +0000
  # '44f23a85d786b4aa', # Wed Jan 21 21:26:54 2015 +0000
  # 'e416dff2dcefa69f', # Wed Jan 21 21:28:22 2015 +0000
  # '5a36bfe017b8c440', # Wed Jan 21 21:29:56 2015 +0000
  # '27bd482c7dd2e4b0', # Wed Jan 21 21:47:32 2015 +0000
  # '156733dbbc0068b3', # Wed Jan 21 21:53:06 2015 +0000
  # 'e0a7b6fde4d924dd', # Wed Jan 21 21:55:04 2015 +0000
  # '277d5afcf3d90017', # Wed Jan 21 21:55:05 2015 +0000
  # 'b20aa015fdfe75da', # Wed Jan 21 21:56:45 2015 +0000
  # 'a141109f58a13bda', # Wed Jan 21 21:58:28 2015 +0000
  # 'a2f6d748a24879d0', # Wed Jan 21 21:58:29 2015 +0000
  # '25d61fca28d2ca5b', # Wed Jan 21 22:00:03 2015 +0000
  # 'a93644fa5e6b9741', # Wed Jan 21 22:01:29 2015 +0000
  # '96f8d4195135b5ba', # Wed Jan 21 22:03:09 2015 +0000
  # 'b132ccda867e4fc8', # Wed Jan 21 22:03:10 2015 +0000
  # '4bc5eddd850f1e72', # Wed Jan 21 22:05:41 2015 +0000
  # '04094bf706d970f1', # Wed Jan 21 22:08:32 2015 +0000
  # 'dc779baf018e7ef4', # Wed Jan 21 22:10:08 2015 +0000
  # '7e344d5d59ca302e', # Wed Jan 21 22:10:09 2015 +0000
  # '3e12039f6acccefc', # Wed Jan 21 22:11:43 2015 +0000
  # '2cb31f691a4357d7', # Wed Jan 21 22:13:17 2015 +0000
  # 'd2b1fcfa150c2e1c', # Wed Jan 21 22:13:18 2015 +0000
  # '88bfd0c0b318796a', # Wed Jan 21 22:18:38 2015 +0000
  # '09525e37b15fad83', # Wed Jan 21 22:24:47 2015 +0000
  # '520e6bb69cb0b2fa', # Wed Jan 21 22:26:49 2015 +0000
  # '0055a3a72acc45fb', # Wed Jan 21 22:29:33 2015 +0000
  # '24fd209fd5257d3e', # Wed Jan 21 22:31:15 2015 +0000
  # 'b7b07fd149ac2b41', # Wed Jan 21 22:36:41 2015 +0000
  # '96fcf6d0c177153a', # Wed Jan 21 22:38:25 2015 +0000
  # '3390495d5d269e22', # Wed Jan 21 22:43:01 2015 +0000
  # 'f946e2446a58f44e', # Wed Jan 21 22:44:40 2015 +0000
  # '17e8905123503b7f', # Wed Jan 21 22:44:41 2015 +0000
  # 'bbc23e733485b6ef', # Wed Jan 21 22:50:15 2015 +0000
  # '1ca44b0b642e3479', # Wed Jan 21 22:58:28 2015 +0000
  # '3b7678d024158307', # Wed Jan 21 23:05:44 2015 +0000
  # 'a2e3cc7a3586e7a2', # Wed Jan 21 23:11:27 2015 +0000
  # '60f701a21bd61db8', # Wed Jan 21 23:16:39 2015 +0000
  # 'f3e52af4a756df54', # Wed Jan 21 23:19:45 2015 +0000
  # 'ae57221ff2622f1e', # Wed Jan 21 23:23:38 2015 +0000
  # '50b8f236ff3db16d', # Wed Jan 21 23:27:45 2015 +0000
  # 'b6274c806784b2af', # Wed Jan 21 23:31:49 2015 +0000
  # 'd030c2a71609cb99', # Wed Jan 21 23:37:17 2015 +0000
  # 'c92575be237e9766', # Wed Jan 21 23:58:27 2015 +0000
)
