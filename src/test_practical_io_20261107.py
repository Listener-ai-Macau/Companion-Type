import ctypes,json,os,tempfile,threading,time,unittest
from pathlib import Path
from practical_io_20261107 import atomic_json

@unittest.skipUnless(os.name=='nt','Actual Windows sharing violation regression')
class WindowsPublication(unittest.TestCase):
    def locked(self,file):
        dll=ctypes.WinDLL('kernel32',use_last_error=True);dll.CreateFileW.argtypes=[ctypes.c_wchar_p,ctypes.c_ulong,ctypes.c_ulong,ctypes.c_void_p,ctypes.c_ulong,ctypes.c_ulong,ctypes.c_void_p];dll.CreateFileW.restype=ctypes.c_void_p;dll.CloseHandle.argtypes=[ctypes.c_void_p]
        handle=dll.CreateFileW(str(file),0x80000000,1,None,3,0,None)
        self.assertNotEqual(handle,ctypes.c_void_p(-1).value)
        return dll,handle
    def test_locked_progress_defers_and_keeps_last_complete_value(self):
        with tempfile.TemporaryDirectory() as folder:
            file=Path(folder)/'state.json';atomic_json(file,{'n':1});dll,handle=self.locked(file)
            try:self.assertFalse(atomic_json(file,{'n':2},progress=True));self.assertEqual(json.loads(file.read_text()),{'n':1})
            finally:dll.CloseHandle(handle)
            self.assertTrue(atomic_json(file,{'n':3},progress=True));self.assertEqual(json.loads(file.read_text()),{'n':3});self.assertEqual(len(list(Path(folder).iterdir())),1)
    def test_durable_write_retries_actual_transient_windows_lock(self):
        with tempfile.TemporaryDirectory() as folder:
            file=Path(folder)/'checkpoint.json';atomic_json(file,{'n':1});dll,handle=self.locked(file)
            release=threading.Thread(target=lambda:(time.sleep(.07),dll.CloseHandle(handle)));release.start()
            self.assertTrue(atomic_json(file,{'n':2}));release.join();self.assertEqual(json.loads(file.read_text()),{'n':2})
    def test_durable_failure_is_not_claimed_saved(self):
        with tempfile.TemporaryDirectory() as folder:
            file=Path(folder)/'checkpoint.json';atomic_json(file,{'n':1});dll,handle=self.locked(file)
            try:
                with self.assertRaises(PermissionError):atomic_json(file,{'n':2})
                self.assertEqual(json.loads(file.read_text()),{'n':1})
            finally:dll.CloseHandle(handle)

if __name__=='__main__':unittest.main()
