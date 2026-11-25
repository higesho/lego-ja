/* dinput8.dll proxy: forwards the exports to the system dinput8.dll */
#include <windows.h>

static HMODULE g_real;
static FARPROC pf_DirectInput8Create, pf_DllCanUnloadNow, pf_DllGetClassObject,
               pf_DllRegisterServer, pf_DllUnregisterServer, pf_GetdfDIJoystick;

void proxy_init(void)
{
    char path[MAX_PATH];
    UINT n = GetSystemDirectoryA(path, MAX_PATH);
    lstrcpyA(path + n, "\\dinput8.dll");
    g_real = LoadLibraryA(path);
    if (!g_real) return;
    pf_DirectInput8Create = GetProcAddress(g_real, "DirectInput8Create");
    pf_DllCanUnloadNow = GetProcAddress(g_real, "DllCanUnloadNow");
    pf_DllGetClassObject = GetProcAddress(g_real, "DllGetClassObject");
    pf_DllRegisterServer = GetProcAddress(g_real, "DllRegisterServer");
    pf_DllUnregisterServer = GetProcAddress(g_real, "DllUnregisterServer");
    pf_GetdfDIJoystick = GetProcAddress(g_real, "GetdfDIJoystick");
}

/* DirectInput8Create is exported here */
HRESULT WINAPI real_DirectInput8Create(HINSTANCE h, DWORD v, REFIID r, LPVOID *o, LPUNKNOWN u)
{
    if (!pf_DirectInput8Create) return E_FAIL;
    return ((HRESULT (WINAPI *)(HINSTANCE, DWORD, REFIID, LPVOID *, LPUNKNOWN))pf_DirectInput8Create)(h, v, r, o, u);
}

__declspec(naked) void p_DllCanUnloadNow(void) { __asm { jmp dword ptr [pf_DllCanUnloadNow] } }
__declspec(naked) void p_DllGetClassObject(void) { __asm { jmp dword ptr [pf_DllGetClassObject] } }
__declspec(naked) void p_DllRegisterServer(void) { __asm { jmp dword ptr [pf_DllRegisterServer] } }
__declspec(naked) void p_DllUnregisterServer(void) { __asm { jmp dword ptr [pf_DllUnregisterServer] } }
__declspec(naked) void p_GetdfDIJoystick(void) { __asm { jmp dword ptr [pf_GetdfDIJoystick] } }

HRESULT WINAPI p_DirectInput8Create(HINSTANCE h, DWORD v, REFIID r, LPVOID *o, LPUNKNOWN u)
{
    HRESULT hr = real_DirectInput8Create(h, v, r, o, u);
#ifdef LOTRJP_TEST
    { HRESULT testio_wrap_dinput(void *di); if (SUCCEEDED(hr)) testio_wrap_dinput(*o); }
#endif
    return hr;
}
