/* LEGO シリーズ 日本語化 — dinput8.dll proxy
   GAME*.DAT の読み込みに割り込み、text.csv などを日本語版に差し替える */
#include <windows.h>
#include <stdio.h>
#include <stdint.h>
#include <stdlib.h>
#include "legojp.h"

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

/* 日本語の Windows では言語 ID 0x411 を英語として扱わせる。
   LEGO Marvel Super Heroes は 0x411 のとき起動時に null ポインタを踏んで落ちる（英語版の不具合）。
   どの言語の列も日本語にしてあるので、ゲームは英語のつもりで日本語を表示する。 */
/* the games pick their text language from the Windows language; the Japanese text is in the English slot,
   so always report English (US). (Marvel also crashes at start-up when it sees Japanese.) */
/* LEGO Batman 3 has its own Japanese text and font: there the pack asks for Japanese (0x411) instead. */
LANGID g_langid = 0x409;
static LANGID fix_lang(LANGID l) { (void)l; return g_langid; }
static LCID fix_lcid(LCID l) { (void)l; return g_langid; }
static LANGID WINAPI h_GetUserDefaultLangID(void) { return fix_lang(GetUserDefaultLangID()); }
static LANGID WINAPI h_GetSystemDefaultLangID(void) { return fix_lang(GetSystemDefaultLangID()); }
static LANGID WINAPI h_GetUserDefaultUILanguage(void) { return fix_lang(GetUserDefaultUILanguage()); }
static LANGID WINAPI h_GetSystemDefaultUILanguage(void) { return fix_lang(GetSystemDefaultUILanguage()); }
static LCID WINAPI h_GetUserDefaultLCID(void) { return fix_lcid(GetUserDefaultLCID()); }
static LCID WINAPI h_GetSystemDefaultLCID(void) { return fix_lcid(GetSystemDefaultLCID()); }
static LCID WINAPI h_GetThreadLocale(void) { return fix_lcid(GetThreadLocale()); }

static void lang_init(void)
{
    iat_hook("KERNEL32.dll", "GetUserDefaultLangID", (void *)h_GetUserDefaultLangID);
    iat_hook("KERNEL32.dll", "GetSystemDefaultLangID", (void *)h_GetSystemDefaultLangID);
    iat_hook("KERNEL32.dll", "GetUserDefaultUILanguage", (void *)h_GetUserDefaultUILanguage);
    iat_hook("KERNEL32.dll", "GetSystemDefaultUILanguage", (void *)h_GetSystemDefaultUILanguage);
    iat_hook("KERNEL32.dll", "GetUserDefaultLCID", (void *)h_GetUserDefaultLCID);
    iat_hook("KERNEL32.dll", "GetSystemDefaultLCID", (void *)h_GetSystemDefaultLCID);
    iat_hook("KERNEL32.dll", "GetThreadLocale", (void *)h_GetThreadLocale);
}

BOOL WINAPI DllMain(HINSTANCE h, DWORD reason, LPVOID r)
{
    if (reason == DLL_PROCESS_ATTACH) {
        char lp[MAX_PATH];
        DisableThreadLibraryCalls(h);
        InitializeCriticalSection(&g_cs);
        proxy_init();
        if (GetEnvironmentVariableA("LEGOJP_LOG", lp, MAX_PATH)) g_log = fopen(lp, "w");
        jlog("legojp start\n");
        dat_init(h);     /* the pack can set g_langid */
#ifdef LEGOJP_TEST
        { char v[16]; if (GetEnvironmentVariableA("LEGOJP_LANGID", v, sizeof v)) g_langid = (LANGID)strtoul(v, NULL, 0); }
#endif
        jlog("langid %x\n", g_langid);
        lang_init();
#ifdef LEGOJP_TEST
        { void testio_init(void); testio_init(); }
#endif
    }
    return TRUE;
}
