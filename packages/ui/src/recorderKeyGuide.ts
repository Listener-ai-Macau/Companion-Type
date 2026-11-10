import type {CompanionV1DeviceTransportState} from '@companion-type/core';

/** Describe the selected device, including offline use after its identity was read. */
export function recorderKeyGuide(device: Pick<CompanionV1DeviceTransportState,'boardId'|'firmwareVersion'> | null | undefined) {
  const version=device?.firmwareVersion;
  if(device?.boardId===0x57424155 && version!=null && version>=66787) return {
    start:'在录音卡模式，短按实体键一次并松开，开始录音。',
    stop:'再短按一次并松开停止，等待保存完成。',
    trial:'短按实体键一次并松开开始，录约 10 秒后，再短按一次并松开停止。',
    highlight:'录音中敲两下机身标记重点；同步后可在这条录音的重点列表中找到。',
    pairing:'首次连接时让设备靠近电脑。若连接窗口尚未打开，短按实体键一次；这也会开始录音，连接后再短按一次停止。',
  };
  if(device?.boardId===0x57424155 && version!=null && version<66787) return {
    start:'长按实体键约 1 秒开始录音；睡着时先短按唤醒。',
    stop:'再长按约 1 秒停止，等待保存完成。',
    trial:'睡着时先短按唤醒。长按实体键约 1 秒开始，录约 10 秒后，再长按约 1 秒停止。',
    highlight:'重点标记方式以这台设备的配套说明为准。',
    pairing:'首次连接时让设备靠近电脑，并按设备的配套说明打开连接窗口。',
  };
  return {
    start:'连接设备后，这里会显示匹配当前设备的实体键用法；也可在“设备与同步”点“开始录音”。',
    stop:'在“设备与同步”点停止，等待保存完成。离线按键用法以设备的配套说明为准。',
    trial:'先连接设备，再按本页显示的实体键用法试录；也可在“设备与同步”开始录音，约 10 秒后停止。',
    highlight:'连接设备后，可查看这台设备支持的重点标记方式。',
    pairing:'首次连接时让设备靠近电脑，并按设备的配套说明打开连接窗口。',
  };
}
