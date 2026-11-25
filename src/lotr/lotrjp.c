/* LEGO The Lord of the Rings 日本語化 — dinput8.dll proxy
   GAME*.DAT の読み込みに割り込み、text.csv などを日本語版に差し替える */
#include <windows.h>
#include <stdio.h>
#include <stdint.h>
#include "lotrjp.h"

void proxy_init(void);
static FILE *g_log;
CRITICAL_SECTION g_cs;

void jlog(const char *fmt, ...)
{
    va_list ap;
    if (!g_log) return;
    va_start(ap, fmt);
    vfprintf(g_log, fmt, ap);
    va_end(ap);
    fflush(g_log);
}

void *iat_hook(const char *dll, const char *func, void *repl)
{
    uint8_t *base = (uint8_t *)GetModuleHandleA(NULL);
    IMAGE_NT_HEADERS *nt = (IMAGE_NT_HEADERS *)(base + ((IMAGE_DOS_HEADER *)base)->e_lfanew);
    IMAGE_DATA_DIRECTORY *dir = &nt->OptionalHeader.DataDirectory[IMAGE_DIRECTORY_ENTRY_IMPORT];
    IMAGE_IMPORT_DESCRIPTOR *imp = (IMAGE_IMPORT_DESCRIPTOR *)(base + dir->VirtualAddress);
    for (; imp->Name; imp++) {
        IMAGE_THUNK_DATA *names, *addrs;
        if (_stricmp((char *)(base + imp->Name), dll)) continue;
        names = (IMAGE_THUNK_DATA *)(base + imp->OriginalFirstThunk);
        addrs = (IMAGE_THUNK_DATA *)(base + imp->FirstThunk);
        for (; names->u1.AddressOfData; names++, addrs++) {
            IMAGE_IMPORT_BY_NAME *ibn;
            if (names->u1.Ordinal & IMAGE_ORDINAL_FLAG) continue;
            ibn = (IMAGE_IMPORT_BY_NAME *)(base + names->u1.AddressOfData);
            if (!strcmp((char *)ibn->Name, func)) {
                void *old = (void *)addrs->u1.Function;
                DWORD prot;
                VirtualProtect(&addrs->u1.Function, 4, PAGE_READWRITE, &prot);
                addrs->u1.Function = (ULONG_PTR)repl;
                VirtualProtect(&addrs->u1.Function, 4, prot, &prot);
                return old;
            }
        }
    }
    return NULL;
}

BOOL WINAPI DllMain(HINSTANCE h, DWORD reason, LPVOID r)
{
    if (reason == DLL_PROCESS_ATTACH) {
        char lp[MAX_PATH];
        DisableThreadLibraryCalls(h);
        InitializeCriticalSection(&g_cs);
        proxy_init();
        if (GetEnvironmentVariableA("LOTRJP_LOG", lp, MAX_PATH)) g_log = fopen(lp, "w");
        jlog("lotrjp start\n");
        dat_init(h);
#ifdef LOTRJP_TEST
        { void testio_init(void); testio_init(); }
#endif
    }
    return TRUE;
}
