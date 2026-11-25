/* GAME*.DAT overlay
   ゲームは GAME*.DAT を CreateFileA で開き、索引を同期 ReadFile で読み、
   各ファイルを SetFilePointerEx + ReadFile で読む。
   ・索引（16 バイト × 件数）を読み込んだ直後に、差し替えるファイルの項目を書き換える
     （オフセット → ファイル末尾より後ろの仮想領域、サイズ → 新しいサイズ、圧縮なし）
   ・仮想領域への読み込みはメモリ上の差し替えデータで答える */
#include <windows.h>
#include <stdint.h>
#include <string.h>
#include <stdlib.h>
#include <compressapi.h>
#include "lotrjp.h"

static HANDLE (WINAPI *o_CreateFileA)(LPCSTR, DWORD, DWORD, LPSECURITY_ATTRIBUTES, DWORD, DWORD, HANDLE);
static BOOL (WINAPI *o_ReadFile)(HANDLE, LPVOID, DWORD, LPDWORD, LPOVERLAPPED);
static BOOL (WINAPI *o_SetFilePointerEx)(HANDLE, LARGE_INTEGER, PLARGE_INTEGER, DWORD);
static BOOL (WINAPI *o_CloseHandle)(HANDLE);

/* ---------- 差し替えデータ（pack） ----------
   "LJP1" u32 count, then count × { u8 dat; u8 namelen; char name[namelen]; u32 origsize; u32 len; data[len] } */
typedef struct {
    int dat;                /* 0 = GAME.DAT, 1 = GAME0.DAT, 2 = GAME1.DAT ... */
    const char *name;
    int namelen;
    uint32_t origsize;
    const uint8_t *data;
    uint32_t len;
} Repl;

static Repl *g_repl;
static int g_nrepl;

typedef struct {
    int idx;                /* file index in the DAT */
    const Repl *r;
    uint64_t voff;          /* virtual offset (multiple of 256) */
} Patch;

typedef struct {
    HANDLE h;
    int dat;
    uint64_t realsize, vbase, vend;
    uint64_t tab_off;       /* file offset of the 16-byte entry table */
    uint32_t nfiles;
    Patch *p;
    int np;
} DatH;

#define MAXH 16
static DatH g_dh[MAXH];

static DatH *dat_of(HANDLE h)
{
    int i;
    if (!h || h == INVALID_HANDLE_VALUE) return NULL;
    for (i = 0; i < MAXH; i++) if (g_dh[i].h == h) return &g_dh[i];
    return NULL;
}

static int read_at(HANDLE h, uint64_t off, void *buf, DWORD n)
{
    LARGE_INTEGER li; DWORD got = 0;
    li.QuadPart = (LONGLONG)off;
    if (!o_SetFilePointerEx(h, li, NULL, FILE_BEGIN)) return 0;
    return o_ReadFile(h, buf, n, &got, NULL) && got == n;
}

/* parse the DAT index with our own handle and find the files to replace */
static void setup_dat(DatH *d, const char *path)
{
    HANDLE h;
    uint32_t hdr[2], off, sz, n, cnt, poolsz, i, k;
    uint8_t *info = NULL;
    LARGE_INTEGER fs;
    int any = 0;
    for (k = 0; k < (uint32_t)g_nrepl; k++) if (g_repl[k].dat == d->dat) any = 1;
    if (!any) return;
    h = o_CreateFileA(path, GENERIC_READ, FILE_SHARE_READ, NULL, OPEN_EXISTING, 0, NULL);
    if (h == INVALID_HANDLE_VALUE) return;
    if (!GetFileSizeEx(h, &fs) || !read_at(h, 0, hdr, 8)) goto out;
    off = hdr[0]; sz = hdr[1];
    {
        uint64_t o64 = off;
        if (off & 0x80000000u) o64 = ((uint64_t)(off ^ 0xffffffffu) << 8) + 0x100;
        info = (uint8_t *)malloc(sz);
        if (!info || !read_at(h, o64, info, sz)) goto out;
        d->tab_off = o64 + 8;
    }
    if (*(int32_t *)info != -5) { jlog("dat %d: unknown version %d\n", d->dat, *(int32_t *)info); goto out; }
    n = *(uint32_t *)(info + 4);
    d->nfiles = n;
    {
        uint32_t p = 8 + n * 16;
        const uint8_t *recs, *pool;
        cnt = *(uint32_t *)(info + p);
        recs = info + p + 4;
        poolsz = *(uint32_t *)(recs + cnt * 12);
        pool = recs + cnt * 12 + 4;
        d->realsize = (uint64_t)fs.QuadPart;
        d->vbase = ((d->realsize + 0xfff) & ~(uint64_t)0xff) + 0x1000;
        d->vend = d->vbase;
        d->p = (Patch *)calloc(g_nrepl, sizeof(Patch));
        for (i = 1; i < cnt; i++) {
            int16_t next = *(int16_t *)(recs + i * 12);
            uint32_t no = *(uint32_t *)(recs + i * 12 + 4);
            int fi;
            const char *nm;
            if (next > 0 || no >= poolsz) continue;
            fi = -next;
            if ((uint32_t)fi >= n) continue;
            nm = (const char *)pool + no;
            for (k = 0; k < (uint32_t)g_nrepl; k++) {
                const Repl *r = &g_repl[k];
                const uint32_t *e = (const uint32_t *)(info + 8 + fi * 16);
                if (r->dat != d->dat || (int)strlen(nm) != r->namelen || _strnicmp(nm, r->name, r->namelen)) continue;
                if (e[2] != r->origsize) { jlog("dat %d: %s size %u != %u (skipped)\n", d->dat, nm, e[2], r->origsize); continue; }
                d->p[d->np].idx = fi;
                d->p[d->np].r = r;
                d->p[d->np].voff = d->vend;
                d->vend = (d->vend + r->len + 0x1ff) & ~(uint64_t)0xff;
                jlog("dat %d: patch #%d %s %u -> %u bytes at %llx\n", d->dat, fi, nm, r->origsize, r->len, d->p[d->np].voff);
                d->np++;
            }
        }
    }
out:
    free(info);
    CloseHandle(h);
}

static HANDLE WINAPI h_CreateFileA(LPCSTR n, DWORD a, DWORD s, LPSECURITY_ATTRIBUTES sa, DWORD c, DWORD f, HANDLE t)
{
    HANDLE h = o_CreateFileA(n, a, s, sa, c, f, t);
    const char *b;
    int dat = -1;
    if (h == INVALID_HANDLE_VALUE || !n) return h;
    b = strrchr(n, 0x5c); b = b ? b + 1 : n;
    if (!_stricmp(b, "GAME.DAT")) dat = 0;
    else if (!_strnicmp(b, "GAME", 4) && b[4] >= '0' && b[4] <= '9' && !_stricmp(b + 5, ".DAT")) dat = 1 + (b[4] - '0');
    if (dat >= 0 && g_nrepl) {
        int i;
        EnterCriticalSection(&g_cs);
        for (i = 0; i < MAXH; i++) if (!g_dh[i].h) {
            memset(&g_dh[i], 0, sizeof g_dh[i]);
            g_dh[i].dat = dat;
            setup_dat(&g_dh[i], n);
            if (g_dh[i].np) g_dh[i].h = h;
            break;
        }
        LeaveCriticalSection(&g_cs);
    }
    return h;
}

static BOOL WINAPI h_CloseHandle(HANDLE h)
{
    DatH *d = dat_of(h);
    if (d) { EnterCriticalSection(&g_cs); free(d->p); memset(d, 0, sizeof *d); LeaveCriticalSection(&g_cs); }
    return o_CloseHandle(h);
}

static BOOL WINAPI h_ReadFile(HANDLE h, LPVOID buf, DWORD n, LPDWORD got, LPOVERLAPPED ov)
{
    DatH *d = dat_of(h);
    LARGE_INTEGER pos = {0}, z = {0};
    BOOL r;
    int i;
    if (!d || ov) return o_ReadFile(h, buf, n, got, ov);
    o_SetFilePointerEx(h, z, &pos, FILE_CURRENT);
    if ((uint64_t)pos.QuadPart >= d->vbase) {
        /* virtual region */
        uint64_t p0 = (uint64_t)pos.QuadPart, p1 = p0 + n;
        LARGE_INTEGER np;
        memset(buf, 0, n);
        for (i = 0; i < d->np; i++) {
            uint64_t a = d->p[i].voff, b2 = a + d->p[i].r->len;
            uint64_t lo = p0 > a ? p0 : a, hi = p1 < b2 ? p1 : b2;
            if (lo < hi) memcpy((uint8_t *)buf + (lo - p0), d->p[i].r->data + (lo - a), (size_t)(hi - lo));
        }
        np.QuadPart = (LONGLONG)p1;
        o_SetFilePointerEx(h, np, NULL, FILE_BEGIN);
        if (got) *got = n;
        return TRUE;
    }
    r = o_ReadFile(h, buf, n, got, ov);
    if (r) {
        /* patch the entry table */
        uint64_t p0 = (uint64_t)pos.QuadPart, p1 = p0 + (got ? *got : n);
        for (i = 0; i < d->np; i++) {
            uint64_t eo = d->tab_off + (uint64_t)d->p[i].idx * 16;
            uint32_t e[4];
            int j;
            if (eo + 16 <= p0 || eo >= p1) continue;
            /* build the new entry from the bytes we have (flags keep their upper bytes) */
            for (j = 0; j < 16; j++) {
                uint64_t a = eo + j;
                ((uint8_t *)e)[j] = (a >= p0 && a < p1) ? ((uint8_t *)buf)[a - p0] : 0;
            }
            e[0] = (uint32_t)(d->p[i].voff >> 8);
            e[1] = e[2] = d->p[i].r->len;
            e[3] &= ~0xffu;
            for (j = 0; j < 16; j++) {
                uint64_t a = eo + j;
                if (a >= p0 && a < p1) ((uint8_t *)buf)[a - p0] = ((uint8_t *)e)[j];
            }
        }
    }
    return r;
}

/* ---------- pack loading ---------- */
static uint8_t *decompress(const uint8_t *src, uint32_t n, uint32_t *outn)
{
    DECOMPRESSOR_HANDLE dh;
    SIZE_T need = 0;
    uint8_t *out = NULL;
    if (n < 8 || memcmp(src, "LJPZ", 4)) return NULL;
    if (!CreateDecompressor(COMPRESS_ALGORITHM_LZMS, NULL, &dh)) return NULL;
    need = *(uint32_t *)(src + 4);
    out = (uint8_t *)malloc(need);
    if (out && !Decompress(dh, src + 8, n - 8, out, need, &need)) { free(out); out = NULL; }
    CloseDecompressor(dh);
    if (out) *outn = (uint32_t)need;
    return out;
}

static void parse_pack(uint8_t *p, uint32_t n)
{
    uint32_t cnt, i, o = 8;
    if (n < 8 || memcmp(p, "LJP1", 4)) return;
    cnt = *(uint32_t *)(p + 4);
    g_repl = (Repl *)calloc(cnt, sizeof(Repl));
    for (i = 0; i < cnt && o + 2 <= n; i++) {
        Repl *r = &g_repl[g_nrepl];
        r->dat = p[o]; r->namelen = p[o + 1]; o += 2;
        r->name = (const char *)p + o; o += r->namelen;
        r->origsize = *(uint32_t *)(p + o); r->len = *(uint32_t *)(p + o + 4); o += 8;
        r->data = p + o; o += r->len;
        if (o > n) break;
        g_nrepl++;
    }
    jlog("pack: %d files\n", g_nrepl);
}

static void load_pack(HINSTANCE self)
{
    uint8_t *raw = NULL, *p;
    uint32_t n = 0, pn = 0;
#ifdef LOTRJP_TEST
    char path[MAX_PATH];
    if (GetEnvironmentVariableA("LOTRJP_PACK", path, MAX_PATH)) {
        HANDLE h = CreateFileA(path, GENERIC_READ, FILE_SHARE_READ, NULL, OPEN_EXISTING, 0, NULL);
        if (h != INVALID_HANDLE_VALUE) {
            DWORD got;
            n = GetFileSize(h, NULL);
            raw = (uint8_t *)malloc(n);
            if (!ReadFile(h, raw, n, &got, NULL) || got != n) { free(raw); raw = NULL; }
            CloseHandle(h);
        }
    }
#endif
    if (!raw) {
        HRSRC rs = FindResourceA(self, MAKEINTRESOURCEA(1), "LOTRJP");
        HGLOBAL g;
        if (!rs || !(g = LoadResource(self, rs))) return;
        raw = (uint8_t *)LockResource(g);
        n = SizeofResource(self, rs);
    }
    p = decompress(raw, n, &pn);
    if (!p) { jlog("pack: decompress failed\n"); return; }
    parse_pack(p, pn);
}

void dat_init(HINSTANCE self)
{
    load_pack(self);
    if (!g_nrepl) return;
    o_SetFilePointerEx = SetFilePointerEx;
    o_CreateFileA = iat_hook("KERNEL32.dll", "CreateFileA", (void *)h_CreateFileA);
    o_ReadFile = iat_hook("KERNEL32.dll", "ReadFile", (void *)h_ReadFile);
    o_CloseHandle = iat_hook("KERNEL32.dll", "CloseHandle", (void *)h_CloseHandle);
    if (!o_CreateFileA) o_CreateFileA = CreateFileA;
    if (!o_ReadFile) o_ReadFile = ReadFile;
    if (!o_CloseHandle) o_CloseHandle = CloseHandle;
}
