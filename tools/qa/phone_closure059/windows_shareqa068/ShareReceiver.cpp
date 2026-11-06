#include <windows.h>
#include <winrt/Windows.ApplicationModel.Activation.h>
#include <winrt/Windows.ApplicationModel.Core.h>
#include <winrt/Windows.ApplicationModel.DataTransfer.h>
#include <winrt/Windows.ApplicationModel.DataTransfer.ShareTarget.h>
#include <winrt/Windows.Data.Json.h>
#include <winrt/Windows.Foundation.Collections.h>
#include <winrt/Windows.Security.Cryptography.h>
#include <winrt/Windows.Security.Cryptography.Core.h>
#include <winrt/Windows.Storage.h>
#include <winrt/Windows.Storage.FileProperties.h>
#include <winrt/Windows.Storage.Streams.h>
#include <winrt/Windows.UI.Core.h>
#include <set>

using namespace winrt;
using namespace Windows::ApplicationModel::Activation;
using namespace Windows::ApplicationModel::Core;
using namespace Windows::ApplicationModel::DataTransfer;
using namespace Windows::ApplicationModel::DataTransfer::ShareTarget;
using namespace Windows::Data::Json;
using namespace Windows::Foundation;
using namespace Windows::Security::Cryptography;
using namespace Windows::Security::Cryptography::Core;
using namespace Windows::Storage;
using namespace Windows::UI::Core;

constexpr wchar_t PublicTitle[] = L"公开虚构Windows内容验收 · 非真实会议";
bool IsPublicTitle(hstring const& title) {
    const std::wstring value(title);
    if (value == PublicTitle || value == L"Windows067-public-transcript" || value == L"Windows067-public-transcript.pdf") return true;
    for (auto ext : {L".txt",L".md",L".docx",L".pdf",L".pptx",L".xlsx",L".mm",L".png",L".srt",L".wav",L".mp3"}) {
        if (value == std::wstring(PublicTitle) + ext || value == std::wstring(PublicTitle) + L"-所选内容" + ext) return true;
    }
    return value == std::wstring(PublicTitle) + L"-所选内容";
}

struct App : implements<App, IFrameworkViewSource, IFrameworkView> {
    CoreWindow window{nullptr};
    IFrameworkView CreateView() { return *this; }
    void Initialize(CoreApplicationView const& view) {
        view.Activated({this, &App::OnActivated});
    }
    void SetWindow(CoreWindow const& value) { window = value; }
    void Load(hstring const&) {}
    void Run() { window.Dispatcher().ProcessEvents(CoreProcessEventsOption::ProcessUntilQuit); }
    void Uninitialize() {}

    fire_and_forget Receive(ShareOperation operation) {
        auto lifetime = get_strong();
        bool publicRequest = false;
        try {
            auto data = operation.Data();
            // Reject other shares before requesting any file or text payload.
            publicRequest = IsPublicTitle(data.Properties().Title());
            if (!publicRequest || !data.Contains(StandardDataFormats::StorageItems())) {
                operation.ReportError(L"这里只接受本轮公开虚构验收文件；未读取分享正文。");
                co_return;
            }
            operation.ReportStarted();
            auto files = co_await data.GetStorageItemsAsync();
            if (files.Size() != 1) throw hresult_invalid_argument(L"Only one public test file is accepted.");
            auto file = files.GetAt(0).try_as<StorageFile>();
            if (!file) throw hresult_invalid_argument(L"Folders are not accepted.");
            std::set<std::wstring> allowed{L".txt",L".md",L".docx",L".pdf",L".pptx",L".xlsx",L".mm",L".png",L".srt",L".wav",L".mp3"};
            if (!allowed.contains(std::wstring(file.FileType()))) throw hresult_invalid_argument(L"Unsupported public test format.");
            auto properties = co_await file.GetBasicPropertiesAsync();
            if (properties.Size() == 0 || properties.Size() > 32 * 1024 * 1024) throw hresult_invalid_argument(L"Public test file size is outside the bounded limit.");
            auto bytes = co_await FileIO::ReadBufferAsync(file);
            if (bytes.Length() != properties.Size()) throw hresult_error(E_FAIL,L"File changed during receipt.");
            auto provider = HashAlgorithmProvider::OpenAlgorithm(HashAlgorithmNames::Sha256());
            auto digest = CryptographicBuffer::EncodeToHexString(provider.HashData(bytes));
            bool readWriteGranted = false;
            try {
                auto probe = co_await file.OpenAsync(FileAccessMode::ReadWrite);
                readWriteGranted = true;
                probe.Close(); // Never write or change the shared source.
            } catch (hresult_error const&) {}
            auto folder = co_await ApplicationData::Current().LocalFolder().CreateFolderAsync(L"public-receipts",CreationCollisionOption::OpenIfExists);
            guid identity{};
            check_hresult(CoCreateGuid(reinterpret_cast<GUID*>(&identity)));
            auto id = to_hstring(identity);
            auto received = co_await folder.CreateFileAsync(id + file.FileType(),CreationCollisionOption::FailIfExists);
            co_await FileIO::WriteBufferAsync(received,bytes);
            JsonObject receipt;
            receipt.Insert(L"state",JsonValue::CreateStringValue(L"ACTUAL_WINDOWS_SHARE_TARGET_FILE_RECEIVED"));
            receipt.Insert(L"title",JsonValue::CreateStringValue(data.Properties().Title()));
            receipt.Insert(L"originalFileName",JsonValue::CreateStringValue(file.Name()));
            receipt.Insert(L"receivedFileName",JsonValue::CreateStringValue(received.Name()));
            receipt.Insert(L"extension",JsonValue::CreateStringValue(file.FileType()));
            receipt.Insert(L"contentType",JsonValue::CreateStringValue(file.ContentType()));
            receipt.Insert(L"bytes",JsonValue::CreateNumberValue(bytes.Length()));
            receipt.Insert(L"sha256",JsonValue::CreateStringValue(digest));
            receipt.Insert(L"copyRequested",JsonValue::CreateBooleanValue(data.RequestedOperation() == DataPackageOperation::Copy));
            receipt.Insert(L"readWriteGranted",JsonValue::CreateBooleanValue(readWriteGranted));
            receipt.Insert(L"sourceWritten",JsonValue::CreateBooleanValue(false));
            receipt.Insert(L"networkCapability",JsonValue::CreateBooleanValue(false));
            receipt.Insert(L"publicSyntheticFixture",JsonValue::CreateBooleanValue(true));
            auto report = co_await folder.CreateFileAsync(id + L".json",CreationCollisionOption::FailIfExists);
            co_await FileIO::WriteTextAsync(report,receipt.Stringify());
            operation.ReportDataRetrieved();
            operation.ReportCompleted();
        } catch (hresult_error const&) {
            if (publicRequest) {
                // Errors never include file paths, unexpected content or private data.
                try { operation.ReportError(L"本机公开文件校验未完成；没有向外部发送数据。"); } catch (...) {}
            }
        } catch (...) {
            try { operation.ReportError(L"本机公开文件校验未完成。"); } catch (...) {}
        }
    }
    void OnActivated(CoreApplicationView const&, IActivatedEventArgs const& args) {
        if (args.Kind() == ActivationKind::ShareTarget) {
            window.Activate();
            Receive(args.as<ShareTargetActivatedEventArgs>().ShareOperation());
        }
    }
};

int __stdcall wWinMain(HINSTANCE,HINSTANCE,PWSTR,int) {
    init_apartment(apartment_type::single_threaded);
    CoreApplication::Run(make<App>());
}
