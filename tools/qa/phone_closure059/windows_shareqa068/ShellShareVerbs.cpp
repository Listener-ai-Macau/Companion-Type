#include <windows.h>
#include <shlobj.h>
#include <wrl/client.h>
#include <iostream>
#include <string>
using Microsoft::WRL::ComPtr;
int wmain(int argc,wchar_t** argv){
 if(argc!=2)return 2;
 std::wstring path=argv[1];
 if(path.find(L"Windows067-public-transcript.pdf")==std::wstring::npos)return 3;
 auto hr=CoInitializeEx(nullptr,COINIT_APARTMENTTHREADED);if(FAILED(hr))return 4;
 PIDLIST_ABSOLUTE absolute=nullptr;
 hr=SHParseDisplayName(path.c_str(),nullptr,&absolute,0,nullptr);
 if(FAILED(hr)){std::cout<<"parse "<<std::hex<<hr;return 5;}
 ComPtr<IShellFolder> folder;PCUITEMID_CHILD child=nullptr;
 hr=SHBindToParent(absolute,IID_PPV_ARGS(&folder),&child);
 if(FAILED(hr)){CoTaskMemFree(absolute);return 6;}
 ComPtr<IContextMenu> menu;
 hr=folder->GetUIObjectOf(nullptr,1,&child,IID_IContextMenu,nullptr,reinterpret_cast<void**>(menu.GetAddressOf()));
 if(FAILED(hr)){CoTaskMemFree(absolute);return 7;}
 HMENU popup=CreatePopupMenu();hr=menu->QueryContextMenu(popup,0,1,0x7fff,CMF_NORMAL|CMF_EXTENDEDVERBS);
 if(FAILED(hr)){DestroyMenu(popup);CoTaskMemFree(absolute);return 8;}
 const unsigned count=HRESULT_CODE(hr);
 std::cout<<"Read-only canonical shell verbs, no menu displayed or command invoked\n";
 for(unsigned i=0;i<count;++i){wchar_t verb[256]{};
  if(SUCCEEDED(menu->GetCommandString(i,GCS_VERBW,nullptr,reinterpret_cast<char*>(verb),256)) && verb[0]){
   int size=WideCharToMultiByte(CP_UTF8,0,verb,-1,nullptr,0,nullptr,nullptr);std::string utf8(size,'\0');WideCharToMultiByte(CP_UTF8,0,verb,-1,utf8.data(),size,nullptr,nullptr);utf8.pop_back();
   std::cout<<i<<" "<<utf8<<"\n";
  }
 }
 DestroyMenu(popup);CoTaskMemFree(absolute);return 0;
}
