/* *.DAT overlay (TT Games LEGO series, DAT versions -3 .. -5)
   ゲームは *.DAT を CreateFileA/W で開き、索引を同期 ReadFile で読み、
   各ファイルを SetFilePointer(Ex) + ReadFile で読む。
   ・索引の項目表（16 バイト × 件数: offset>>8, zsize, size, flags）を読み込んだ直後に、
     差し替えるファイルの項目を書き換える（オフセット → ファイル末尾より後ろの仮想領域、サイズ → 新しいサイズ、圧縮なし）
   ・仮想領域への読み込みはメモリ上の差し替えデータで答える
   差し替えは DAT のファイル名・項目番号・元の大きさで指定する（大きさが合わなければ差し替えない）。 */
#include <windows.h>
#include <stdint.h>
#include <string.h>
#include <stdlib.h>
#include <compressapi.h>
#include "legojp.h"

static HANDLE (WINAPI *o_CreateFileA)(LPCSTR, DWORD, DWORD, LPSECURITY_ATTRIBUTES, DWORD, DWORD, HANDLE);
static HANDLE (WINAPI *o_CreateFileW)(LPCWSTR, DWORD, DWORD, LPSECURITY_ATTRIBUTES, DWORD, DWORD, HANDLE);
static BOOL (WINAPI *o_ReadFile)(HANDLE, LPVOID, DWORD, LPDWORD, LPOVERLAPPED);
static BOOL (WINAPI *o_SetFilePointerEx)(HANDLE, LARGE_INTEGER, PLARGE_INTEGER, DWORD);
static BOOL (WINAPI *o_CloseHandle)(HANDLE);

/* ---------- 差し替えデータ（pack） ----------
   "LJP2" u32 count, then count × { u8 datlen; char dat[datlen]; u8 namelen; char name[namelen];
                                     u32 index; u32 origsize; u32 len; data[len] } */
typedef struct {
    const char *dat; int datlen;
    const char *name; int namelen;
    uint32_t index, origsize;
    const uint8_t *data;
    uint32_t len;
} Repl;

static Repl *g_repl;
static int g_nrepl;
static int g_logreads;   /* test build: log which DAT entries the game reads (LEGOJP_LOGREADS) */

typedef struct {
    uint32_t idx;
    const Repl *r;
    uint64_t voff;          /* virtual offset (multiple of 256) */
} Patch;

typedef struct {
    HANDLE h;
    uint64_t realsize, vbase, vend;
    uint64_t tab_off;       /* file offset of the 16-byte entry table */
    uint32_t nfiles;
    Patch *p;
    int np;
#ifdef LEGOJP_TEST
    char name[64];
    uint64_t *offs;         /* sorted (file offset << 16 | entry index) for read logging */
    uint8_t *seen;
#endif
} DatH;

#define MAXH 32
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

static int name_is(const char *a, int alen, const char *base)
{
    return (int)strlen(base) == alen && !_strnicmp(base, a, alen);
}

#ifdef LEGOJP_TEST
static int cmp64(const void *a, const void *b)
{
    uint64_t x = *(const uint64_t *)a, y = *(const uint64_t *)b;
    return x < y ? -1 : x > y;
}
#endif

/* parse the DAT index with our own handle and find the files to replace. base = DAT file name (no dir) */
static int setup_dat(DatH *d, HANDLE h, const char *base)
{
    uint32_t hdr[2], off, sz, n, i, k;
    uint8_t *info = NULL;
    LARGE_INTEGER fs;
    int any = 0;
    for (k = 0; k < (uint32_t)g_nrepl; k++) if (name_is(g_repl[k].dat, g_repl[k].datlen, base)) any = 1;
#ifndef LEGOJP_TEST
    if (!any) return 0;
#endif
    if (!GetFileSizeEx(h, &fs) || !read_at(h, 0, hdr, 8)) goto out;
    off = hdr[0]; sz = hdr[1];
    {
        uint64_t o64 = off;
        if (off & 0x80000000u) o64 = ((uint64_t)(off ^ 0xffffffffu) << 8) + 0x100;
        if (sz < 8 || sz > 64u << 20) goto out;
        info = (uint8_t *)malloc(sz);
        if (!info || !read_at(h, o64, info, sz)) goto out;
        d->tab_off = o64 + 8;
    }
    n = *(uint32_t *)(info + 4);
    if (*(int32_t *)info > -1 || *(int32_t *)info < -20 || 8 + (uint64_t)n * 16 > sz) { jlog("%s: unknown index\n", base); goto out; }
    d->nfiles = n;
    d->realsize = (uint64_t)fs.QuadPart;
    d->vbase = ((d->realsize + 0xfff) & ~(uint64_t)0xff) + 0x1000;
    d->vend = d->vbase;
    d->p = (Patch *)calloc(g_nrepl + 1, sizeof(Patch));
    for (k = 0; k < (uint32_t)g_nrepl; k++) {
        const Repl *r = &g_repl[k];
        const uint32_t *e;
        if (!name_is(r->dat, r->datlen, base)) continue;
        if (r->index >= n) { jlog("%s: #%u out of range (skipped)\n", base, r->index); continue; }
        e = (const uint32_t *)(info + 8 + r->index * 16);
        if (e[2] != r->origsize) { jlog("%s: #%u %.*s size %u != %u (skipped)\n", base, r->index, r->namelen, r->name, e[2], r->origsize); continue; }
        d->p[d->np].idx = r->index;
        d->p[d->np].r = r;
        d->p[d->np].voff = d->vend;
        d->vend = (d->vend + r->len + 0x1ff) & ~(uint64_t)0xff;
        jlog("%s: patch #%u %.*s %u -> %u bytes at %llx\n", base, r->index, r->namelen, r->name, r->origsize, r->len, d->p[d->np].voff);
        d->np++;
    }
#ifdef LEGOJP_TEST
    lstrcpynA(d->name, base, sizeof d->name);
    d->offs = (uint64_t *)malloc(sizeof(uint64_t) * (n ? n : 1));
    d->seen = (uint8_t *)calloc(n ? n : 1, 1);
    for (i = 0; i < n; i++) d->offs[i] = ((uint64_t)(*(uint32_t *)(info + 8 + i * 16)) << 8 << 16) | i;
    qsort(d->offs, n, sizeof(uint64_t), cmp64);
    any = 1;
#else
    (void)i;
#endif
out:
    free(info);
    return any && d->nfiles;
}

/* LEGO Star Wars: The Complete Saga passes a fixed size of 2 MB (0x200000) to D3DX when it creates a font
   texture from the font file ("mov [eax+1Ch], ecx / mov dword [eax+20h], 200000h"). The Japanese font
   texture is larger, so raise that size. The exe is unpacked at run time, so this runs on the first DAT open. */
static void patch_tex_size(void)
{
    static const uint8_t pat[] = { 0x89, 0x48, 0x1C, 0xC7, 0x40, 0x20, 0x00, 0x00, 0x20, 0x00 };
    static int done;
    uint8_t *mod = (uint8_t *)GetModuleHandleA(NULL), *p, *end, *hit = NULL;
    IMAGE_NT_HEADERS *nt;
    int n = 0;
    if (done) return;
    done = 1;
    nt = (IMAGE_NT_HEADERS *)(mod + ((IMAGE_DOS_HEADER *)mod)->e_lfanew);
    p = mod + nt->OptionalHeader.BaseOfCode;
    end = p + nt->OptionalHeader.SizeOfCode - sizeof pat;
    for (; p < end; p++) if (p[0] == 0x89 && !memcmp(p, pat, sizeof pat)) { hit = p; n++; }
    if (n == 1) {
        DWORD old;
        if (VirtualProtect(hit + 6, 4, PAGE_EXECUTE_READWRITE, &old)) {
            *(uint32_t *)(hit + 6) = 0x01000000;
            VirtualProtect(hit + 6, 4, old, &old);
            FlushInstructionCache(GetCurrentProcess(), hit + 6, 4);
            jlog("texture size limit patched at %p\n", hit);
        }
    }
}

/* LEGO Star Wars: The Complete Saga keeps the PC settings menu words in the exe: per language a table of
   40 {u32 id, const char *text} pairs. Point the English tables (found by id 1 = "Quit to Windows") at Japanese. */
static const char *const g_menu_ja[39] = {
    "終了", "Windows に戻る", "デモメニューに戻る", "ゲームに戻る", "低", "中", "高", "再開",
    "決定", "やめる", "戻る", "はい", "いいえ", "OK", "キャンセル", "オン", "オフ",
    "初期設定に戻す", "映像設定", "画面解像度", "リフレッシュレート", "垂直同期", "アスペクト比",
    "高画質グラフィック", "画面解像度に合わせる", "現在の設定を使う", "テクスチャの品質", "元に戻す",
    "変更を反映するには、ゲームを再起動してください。", "エフェクト設定", "フルシーン・アンチエイリアス",
    "外部で設定済み", "影", "ブルーム", "被写界深度", "スピードブラー", "動的ライトの品質",
    "エッジ・アンチエイリアス", "操作方法を表示",
};

static void patch_menu_strings(void)
{
    static const char key[] = "Quit to Windows";
    uint8_t *mod = (uint8_t *)GetModuleHandleA(NULL), *s = NULL;
    IMAGE_NT_HEADERS *nt = (IMAGE_NT_HEADERS *)(mod + ((IMAGE_DOS_HEADER *)mod)->e_lfanew);
    uint8_t *end = mod + nt->OptionalHeader.SizeOfImage;
    int pass, ntab = 0;
    for (pass = 0; pass < 2; pass++) {
        uint8_t *r = mod;
        MEMORY_BASIC_INFORMATION mbi;
        while (r < end && VirtualQuery(r, &mbi, sizeof mbi)) {
            uint8_t *rb = (uint8_t *)mbi.BaseAddress, *re = rb + mbi.RegionSize, *q;
            if (re > end) re = end;
            if (mbi.State == MEM_COMMIT && !(mbi.Protect & (PAGE_NOACCESS | PAGE_GUARD)) && re - rb > 64) {
                if (pass == 0) {      /* the English string */
                    for (q = rb; q + sizeof key <= re; q++)
                        if (*q == 'Q' && !memcmp(q, key, sizeof key)) { s = q; break; }
                    if (s) break;
                } else {              /* the tables that point at it: {0, x} {1, s} ... */
                    for (q = rb + 8; q + 40 * 8 <= re; q += 4) {
                        if (*(uint32_t *)q == 1 && *(uint8_t **)(q + 4) == s && *(uint32_t *)(q - 8) == 0) {
                            uint8_t *t = q - 8;
                            DWORD old;
                            int j;
                            if (VirtualProtect(t, 40 * 8, PAGE_READWRITE, &old)) {
                                for (j = 0; j < 40; j++) {
                                    uint32_t id = *(uint32_t *)(t + j * 8);
                                    if (id < 39) *(const char **)(t + j * 8 + 4) = g_menu_ja[id];
                                }
                                VirtualProtect(t, 40 * 8, old, &old);
                                ntab++;
                            }
                        }
                    }
                }
            }
            r = rb + mbi.RegionSize;
        }
        if (!s) return;
    }
    if (ntab) jlog("menu string tables patched: %d\n", ntab);
}

static void on_open(HANDLE h, const char *base)
{
    const char *dot = strrchr(base, '.');
    int i;
    static int once;
    if (h == INVALID_HANDLE_VALUE || !dot || _stricmp(dot, ".DAT")) return;
    patch_tex_size();
    if (!once) { once = 1; patch_menu_strings(); }
    EnterCriticalSection(&g_cs);
    for (i = 0; i < MAXH; i++) if (!g_dh[i].h) {
        memset(&g_dh[i], 0, sizeof g_dh[i]);
        if (setup_dat(&g_dh[i], h, base)) g_dh[i].h = h;
        else { free(g_dh[i].p); memset(&g_dh[i], 0, sizeof g_dh[i]); }
        break;
    }
    LeaveCriticalSection(&g_cs);
    {   /* restore the file position for the game */
        LARGE_INTEGER z = {0};
        o_SetFilePointerEx(h, z, NULL, FILE_BEGIN);
    }
}

static HANDLE WINAPI h_CreateFileA(LPCSTR n, DWORD a, DWORD s, LPSECURITY_ATTRIBUTES sa, DWORD c, DWORD f, HANDLE t)
{
    HANDLE h = o_CreateFileA(n, a, s, sa, c, f, t);
    const char *b, *b2;
    if (h == INVALID_HANDLE_VALUE || !n || !g_nrepl && !g_logreads) return h;
    b = strrchr(n, 0x5c); b2 = strrchr(n, '/');
    if (b2 > b) b = b2;
    b = b ? b + 1 : n;
    on_open(h, b);
    return h;
}

static HANDLE WINAPI h_CreateFileW(LPCWSTR n, DWORD a, DWORD s, LPSECURITY_ATTRIBUTES sa, DWORD c, DWORD f, HANDLE t)
{
    HANDLE h = o_CreateFileW(n, a, s, sa, c, f, t);
    const wchar_t *b, *b2;
    char nb[MAX_PATH];
    if (h == INVALID_HANDLE_VALUE || !n || !g_nrepl && !g_logreads) return h;
    b = wcsrchr(n, 0x5c); b2 = wcsrchr(n, L'/');
    if (b2 > b) b = b2;
    b = b ? b + 1 : n;
    if (!WideCharToMultiByte(CP_ACP, 0, b, -1, nb, sizeof nb, NULL, NULL)) return h;
    on_open(h, nb);
    return h;
}

static BOOL WINAPI h_CloseHandle(HANDLE h)
{
    DatH *d = dat_of(h);
    if (d) {
        EnterCriticalSection(&g_cs);
        free(d->p);
#ifdef LEGOJP_TEST
        free(d->offs); free(d->seen);
#endif
        memset(d, 0, sizeof *d);
        LeaveCriticalSection(&g_cs);
    }
    return o_CloseHandle(h);
}

#ifdef LEGOJP_TEST
static void log_read(DatH *d, uint64_t p0)
{
    /* find the entry starting at p0 */
    int lo = 0, hi = (int)d->nfiles - 1;
    while (lo <= hi) {
        int mid = (lo + hi) / 2;
        uint64_t o = d->offs[mid] >> 16;
        if (o < p0) lo = mid + 1;
        else if (o > p0) hi = mid - 1;
        else {
            uint32_t idx;
            while (mid > 0 && (d->offs[mid - 1] >> 16) == p0) mid--;
            idx = (uint32_t)(d->offs[mid] & 0xffff);
            if (idx < d->nfiles && !d->seen[idx]) { d->seen[idx] = 1; jlog("read %s #%u\n", d->name, idx); }
            return;
        }
    }
}
#endif

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
            if (p0 == a) jlog("vread %.*s #%u\n", d->p[i].r->namelen, d->p[i].r->name, d->p[i].idx);
        }
        np.QuadPart = (LONGLONG)p1;
        o_SetFilePointerEx(h, np, NULL, FILE_BEGIN);
        if (got) *got = n;
        return TRUE;
    }
#ifdef LEGOJP_TEST
    if (d->offs) log_read(d, (uint64_t)pos.QuadPart);
#endif
    r = o_ReadFile(h, buf, n, got, ov);
    if (r) {
        /* patch the entry table */
        uint64_t p0 = (uint64_t)pos.QuadPart, p1 = p0 + (got ? *got : n);
        for (i = 0; i < d->np; i++) {
            uint64_t eo = d->tab_off + (uint64_t)d->p[i].idx * 16;
            uint32_t e[4];
            int j;
            if (eo + 16 <= p0 || eo >= p1) continue;
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
    if (n < 8 || memcmp(p, "LJP2", 4)) return;
    cnt = *(uint32_t *)(p + 4);
    g_repl = (Repl *)calloc(cnt + 1, sizeof(Repl));
    for (i = 0; i < cnt && o + 2 <= n; i++) {
        Repl *r = &g_repl[g_nrepl];
        r->datlen = p[o++]; r->dat = (const char *)p + o; o += r->datlen;
        r->namelen = p[o++]; r->name = (const char *)p + o; o += r->namelen;
        if (o + 12 > n) break;
        r->index = *(uint32_t *)(p + o); r->origsize = *(uint32_t *)(p + o + 4); r->len = *(uint32_t *)(p + o + 8); o += 12;
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
#ifdef LEGOJP_TEST
    char path[MAX_PATH];
    if (GetEnvironmentVariableA("LEGOJP_PACK", path, MAX_PATH)) {
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
        HRSRC rs = FindResourceA(self, MAKEINTRESOURCEA(1), "LEGOJP");
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
#ifdef LEGOJP_TEST
    {
        char v[8];
        g_logreads = GetEnvironmentVariableA("LEGOJP_LOGREADS", v, sizeof v) > 0;
    }
#endif
    if (!g_nrepl && !g_logreads) return;
    o_SetFilePointerEx = SetFilePointerEx;
    o_CreateFileA = iat_hook("KERNEL32.dll", "CreateFileA", (void *)h_CreateFileA);
    o_CreateFileW = iat_hook("KERNEL32.dll", "CreateFileW", (void *)h_CreateFileW);
    o_ReadFile = iat_hook("KERNEL32.dll", "ReadFile", (void *)h_ReadFile);
    o_CloseHandle = iat_hook("KERNEL32.dll", "CloseHandle", (void *)h_CloseHandle);
    if (!o_CreateFileA) o_CreateFileA = CreateFileA;
    if (!o_CreateFileW) o_CreateFileW = CreateFileW;
    if (!o_ReadFile) o_ReadFile = ReadFile;
    if (!o_CloseHandle) o_CloseHandle = CloseHandle;
}
