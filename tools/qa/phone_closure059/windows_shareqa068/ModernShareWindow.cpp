#include <windows.h>
#include <shlobj.h>
#include <wrl/client.h>
#include <wrl/implements.h>
#include <servprov.h>
#include <iostream>
#include <string>
using Microsoft::WRL::ComPtr;
class WindowSite : public Microsoft::WRL::RuntimeClass<Microsoft::WRL::RuntimeClassFlags<Microsoft::WRL::ClassicCom>,IServiceProvider,IOleWindow>{
 HWND owner;
public:
 explicit WindowSite(HWND value):owner(value){}
 IFACEMETHODIMP GetWindow(HWND* result) override {if(!result)return E_POINTER;*result=owner;std::cout<<"Site GetWindow valid="<<IsWindow(owner)<<"\n";std::cout.flush();return S_OK;}
 IFACEMETHODIMP ContextSensitiveHelp(BOOL) override {return E_NOTIMPL;}
 IFACEMETHODIMP QueryService(REFGUID,REFIID iid,void** result) override {return QueryInterface(iid,result);}
};
std::wstring publicPath;
HRESULT Share(HWND owner){
 PIDLIST_ABSOLUTE absolute=nullptr;HRESULT hr=SHParseDisplayName(publicPath.c_str(),nullptr,&absolute,0,nullptr);if(FAILED(hr))return hr;
 struct FreePidl{PIDLIST_ABSOLUTE p;~FreePidl(){CoTaskMemFree(p);}} guard{absolute};
 ComPtr<IShellFolder> folder;PCUITEMID_CHILD child=nullptr;hr=SHBindToParent(absolute,IID_PPV_ARGS(&folder),&child);if(FAILED(hr))return hr;
 ComPtr<IContextMenu> menu;hr=folder->GetUIObjectOf(owner,1,&child,IID_IContextMenu,nullptr,reinterpret_cast<void**>(menu.GetAddressOf()));if(FAILED(hr))return hr;
 auto windowSite=Microsoft::WRL::Make<WindowSite>(owner);ComPtr<IObjectWithSite> withSite;
 auto siteResult=menu.As(&withSite);if(SUCCEEDED(siteResult))siteResult=withSite->SetSite(static_cast<IServiceProvider*>(windowSite.Get()));
 std::cout<<"Context menu site result 0x"<<std::hex<<siteResult<<"\n";std::cout.flush();
 HMENU popup=CreatePopupMenu();if(!popup)return HRESULT_FROM_WIN32(GetLastError());
 struct FreeMenu{HMENU h;~FreeMenu(){DestroyMenu(h);}} menuGuard{popup};
 hr=menu->QueryContextMenu(popup,0,1,0x7fff,CMF_NORMAL|CMF_EXTENDEDVERBS);if(FAILED(hr))return hr;
 for(unsigned offset=0;offset<HRESULT_CODE(hr);++offset){
  wchar_t verb[256]{};HRESULT got=menu->GetCommandString(offset,GCS_VERBW,nullptr,reinterpret_cast<char*>(verb),256);
  if(SUCCEEDED(got)&&_wcsicmp(verb,L"Windows.ModernShare")==0){
   CMINVOKECOMMANDINFO info{};info.cbSize=sizeof(info);info.hwnd=owner;info.lpVerb=MAKEINTRESOURCEA(offset);info.nShow=SW_SHOWNORMAL;
   std::cout<<"Invoking exact observed Windows.ModernShare, no recipient chosen\n";std::cout.flush();return menu->InvokeCommand(&info);
  }
 }
 return HRESULT_FROM_WIN32(ERROR_NOT_SUPPORTED);
}
LRESULT CALLBACK WndProc(HWND hwnd,UINT msg,WPARAM wp,LPARAM lp){
 if(msg==WM_COMMAND&&LOWORD(wp)==100){auto hr=Share(hwnd);std::cout<<"ModernShare result 0x"<<std::hex<<hr<<"\n";std::cout.flush();return 0;}
 if(msg==WM_DESTROY){PostQuitMessage(0);return 0;}
 return DefWindowProcW(hwnd,msg,wp,lp);
}
int wmain(int argc,wchar_t** argv){
 if(argc!=2)return 2;publicPath=argv[1];if(publicPath.find(L"Windows067-public-transcript.pdf")==std::wstring::npos)return 3;
 if(FAILED(CoInitializeEx(nullptr,COINIT_APARTMENTTHREADED)))return 4;
 WNDCLASSW wc{};wc.lpfnWndProc=WndProc;wc.hInstance=GetModuleHandleW(nullptr);wc.lpszClassName=L"CompanionModernShare069";if(!RegisterClassW(&wc))return 5;
 auto hwnd=CreateWindowW(wc.lpszClassName,L"Companion 本机文件分享验证 · 公开资料",WS_OVERLAPPEDWINDOW,CW_USEDEFAULT,CW_USEDEFAULT,1000,740,nullptr,nullptr,wc.hInstance,nullptr);if(!hwnd)return 6;
 CreateWindowW(L"BUTTON",L"打开系统文件分享",WS_CHILD|WS_VISIBLE|BS_PUSHBUTTON,30,35,420,55,hwnd,reinterpret_cast<HMENU>(100),wc.hInstance,nullptr);
 ShowWindow(hwnd,SW_SHOWMINNOACTIVE);MSG message{};while(GetMessageW(&message,nullptr,0,0)>0){TranslateMessage(&message);DispatchMessageW(&message);}return 0;
}
