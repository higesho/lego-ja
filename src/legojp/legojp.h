#pragma once
#include <windows.h>
void jlog(const char *fmt, ...);
void *iat_hook(const char *dll, const char *func, void *repl);
void dat_init(HINSTANCE h);
extern CRITICAL_SECTION g_cs;
