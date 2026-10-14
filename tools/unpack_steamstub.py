#!/usr/bin/env python3
"""Statically unpack the Steam DRM wrapper (SteamStub 2.1, x86) of an EXE.

The Steam release of LEGO Star Wars: The Complete Saga wraps
LEGOStarWarsSaga.exe in Valve's SteamStub: a `.bind` section holds the
loader, the entry point is moved there and the code section is
AES-encrypted. Nothing is executed here: the loader's steps are replayed
in Python and the result is written as a plain PE with the original entry
point and code, without the `.bind` section.

  entry stub (.bind)   copies a header (n dwords at a fixed VA) and undoes
                       its chained XOR; the header gives the payload's VA,
                       size and XOR key
  payload              chained XOR again (first dword = the key); holds
                       the original entry point, the code section's VA and
                       size, an AES-256 key and 32 "stolen" bytes
  SteamDRMP.dll        XTEA-CBC encrypted in .bind, mapped by the stub; its
                       `start` export checks Steam, then decrypts
                       stolen + code: the first block in ECB gives the IV,
                       the rest is CBC with PKCS#7 padding, written over
                       the code section; returns the original entry point

The payload offsets below are the ones SteamDRMP.dll's `start` reads in
this build of the wrapper; every step is checked (key match, entry point
inside the code, valid padding), so another build fails loudly instead of
producing garbage.

Usage: python3 -I tools/unpack_steamstub.py LEGOStarWarsSaga.exe -o unpacked/LEGOStarWarsSaga.exe
"""

import argparse
import os
import struct
import sys

# Entry stub: push ebx/ecx/edx/esi/edi/ebp; mov ebp, esp; sub esp, 0x1000;
# mov [ebp-0x88], <header VA>
ENTRY_SIG = bytes.fromhex("53 51 52 56 57 55 8b ec 81 ec 00 10 00 00 c7 85 78 ff ff ff")

# Header fields (byte offsets after decoding).
H_PAYLOAD_KEY = 0x20
H_PAYLOAD_VA = 0x24
H_PAYLOAD_SIZE = 0x28

# Payload fields (byte offsets), as SteamDRMP.dll's start() reads them.
P_FLAGS = 0x344
P_CODE_VA = 0xA2C
P_STOLEN = 0xC34  # 0x20 bytes
P_CODE_SIZE = 0xD24
P_AES_KEY = 0xD28  # 0x20 bytes
P_OEP = 0xFA0
FLAG_NO_ENCRYPTION = 0x4


def u32(b, o):
    return struct.unpack_from("<I", b, o)[0]


def u16(b, o):
    return struct.unpack_from("<H", b, o)[0]


def chained_xor(data, key, start=0):
    """Each dword is XORed with the previous encrypted dword (key first)."""
    out = bytearray(data)
    for o in range(start, len(out) - 3, 4):
        v = u32(out, o)
        struct.pack_into("<I", out, o, v ^ key)
        key = v
    return out


# --- AES-256 decryption (table form, FIPS-197 equivalent inverse cipher) ---

def _aes_tables():
    exp, log = [0] * 256, [0] * 256
    x = 1
    for i in range(255):
        exp[i], log[x] = x, i
        x ^= ((x << 1) ^ (0x1B if x & 0x80 else 0)) & 0xFF  # x *= 3
    sbox = [0x63] * 256
    for a in range(1, 256):
        s = exp[(255 - log[a]) % 255]
        r = s
        for _ in range(4):
            s = ((s << 1) | (s >> 7)) & 0xFF
            r ^= s
        sbox[a] = r ^ 0x63
    inv = [0] * 256
    for a in range(256):
        inv[sbox[a]] = a

    def mul(a, b):
        return exp[(log[a] + log[b]) % 255] if a and b else 0

    td0 = [(mul(inv[x], 14) << 24) | (mul(inv[x], 9) << 16) |
           (mul(inv[x], 13) << 8) | mul(inv[x], 11) for x in range(256)]
    ror = lambda w, n: ((w >> n) | (w << (32 - n))) & 0xFFFFFFFF  # noqa: E731
    return (sbox, inv, td0, [ror(w, 8) for w in td0],
            [ror(w, 16) for w in td0], [ror(w, 24) for w in td0])


SBOX, INV_SBOX, TD0, TD1, TD2, TD3 = _aes_tables()


def aes256_decrypt_keys(key):
    w = list(struct.unpack(">8I", key))
    rcon = 1
    for i in range(8, 60):
        t = w[i - 1]
        if i % 8 == 0:
            t = ((t << 8) | (t >> 24)) & 0xFFFFFFFF
            t = (SBOX[t >> 24] << 24 | SBOX[(t >> 16) & 0xFF] << 16 |
                 SBOX[(t >> 8) & 0xFF] << 8 | SBOX[t & 0xFF]) ^ (rcon << 24)
            rcon = ((rcon << 1) ^ (0x1B if rcon & 0x80 else 0)) & 0xFF
        elif i % 8 == 4:
            t = (SBOX[t >> 24] << 24 | SBOX[(t >> 16) & 0xFF] << 16 |
                 SBOX[(t >> 8) & 0xFF] << 8 | SBOX[t & 0xFF])
        w.append(w[i - 8] ^ t)
    rounds = [w[4 * r:4 * r + 4] for r in range(15)][::-1]
    # InvMixColumns on the middle round keys (TD of SBOX[b] = InvMixColumns of b).
    for r in range(1, 14):
        rounds[r] = [TD0[SBOX[k >> 24]] ^ TD1[SBOX[(k >> 16) & 0xFF]] ^
                     TD2[SBOX[(k >> 8) & 0xFF]] ^ TD3[SBOX[k & 0xFF]] for k in rounds[r]]
    return rounds


def aes256_decrypt_block(rk, block):
    s0, s1, s2, s3 = struct.unpack(">4I", block)
    k = rk[0]
    s0, s1, s2, s3 = s0 ^ k[0], s1 ^ k[1], s2 ^ k[2], s3 ^ k[3]
    for r in range(1, 14):
        k = rk[r]
        s0, s1, s2, s3 = (
            TD0[s0 >> 24] ^ TD1[(s3 >> 16) & 0xFF] ^ TD2[(s2 >> 8) & 0xFF] ^ TD3[s1 & 0xFF] ^ k[0],
            TD0[s1 >> 24] ^ TD1[(s0 >> 16) & 0xFF] ^ TD2[(s3 >> 8) & 0xFF] ^ TD3[s2 & 0xFF] ^ k[1],
            TD0[s2 >> 24] ^ TD1[(s1 >> 16) & 0xFF] ^ TD2[(s0 >> 8) & 0xFF] ^ TD3[s3 & 0xFF] ^ k[2],
            TD0[s3 >> 24] ^ TD1[(s2 >> 16) & 0xFF] ^ TD2[(s1 >> 8) & 0xFF] ^ TD3[s0 & 0xFF] ^ k[3])
    k = rk[14]
    i = INV_SBOX
    return struct.pack(
        ">4I",
        (i[s0 >> 24] << 24 | i[(s3 >> 16) & 0xFF] << 16 | i[(s2 >> 8) & 0xFF] << 8 | i[s1 & 0xFF]) ^ k[0],
        (i[s1 >> 24] << 24 | i[(s0 >> 16) & 0xFF] << 16 | i[(s3 >> 8) & 0xFF] << 8 | i[s2 & 0xFF]) ^ k[1],
        (i[s2 >> 24] << 24 | i[(s1 >> 16) & 0xFF] << 16 | i[(s0 >> 8) & 0xFF] << 8 | i[s3 & 0xFF]) ^ k[2],
        (i[s3 >> 24] << 24 | i[(s2 >> 16) & 0xFF] << 16 | i[(s1 >> 8) & 0xFF] << 8 | i[s0 & 0xFF]) ^ k[3])


def decrypt_code(key, data):
    """First block (ECB) is the IV; the rest is AES-256-CBC, PKCS#7 padded."""
    rk = aes256_decrypt_keys(key)
    prev = aes256_decrypt_block(rk, data[:16])
    out = bytearray()
    for o in range(16, len(data), 16):
        c = data[o:o + 16]
        p = aes256_decrypt_block(rk, c)
        out += bytes(a ^ b for a, b in zip(p, prev))
        prev = c
    pad = out[-1]
    if not 1 <= pad <= 16 or out[-pad:] != bytes([pad]) * pad:
        sys.exit("code section: bad padding after decryption (wrong key?)")
    return out[:-pad]


class Image:
    def __init__(self, data):
        self.file = bytearray(data)
        self.pe = u32(data, 0x3C)
        if data[self.pe:self.pe + 4] != b"PE\0\0":
            sys.exit("not a PE file")
        self.nsec = u16(data, self.pe + 6)
        self.opt = self.pe + 0x18
        self.sec_table = self.opt + u16(data, self.pe + 0x14)
        self.base = u32(data, self.opt + 0x1C)
        self.entry = u32(data, self.opt + 0x10)
        self.sections = []
        for i in range(self.nsec):
            s = self.sec_table + i * 0x28
            name = data[s:s + 8].rstrip(b"\0").decode("latin1")
            vsize, va, raw_size, raw_ptr = struct.unpack_from("<4I", data, s + 8)
            self.sections.append((name, va, vsize, raw_ptr, raw_size))

    def off(self, rva):
        for _, va, vsize, raw_ptr, raw_size in self.sections:
            if va <= rva < va + max(vsize, raw_size):
                if rva - va >= raw_size:
                    sys.exit("RVA %#x is not backed by the file" % rva)
                return raw_ptr + rva - va
        sys.exit("RVA %#x is outside every section" % rva)

    def read(self, va, n):
        o = self.off(va - self.base)
        return bytes(self.file[o:o + n])


def unpack(img):
    e = img.off(img.entry)
    f = img.file
    if f[e:e + len(ENTRY_SIG)] != ENTRY_SIG:
        sys.exit("entry is not the SteamStub 2.1 loader (already unpacked?)")
    header_va = u32(f, e + 0x14)
    # mov esi, [ebp-0x88]; mov ecx, <dwords>; ... mov [ebp-0x42c], <key>
    if f[e + 0x18:e + 0x1F] != bytes.fromhex("8b b5 78 ff ff ff b9") or \
       f[e + 0x37:e + 0x3D] != bytes.fromhex("c7 85 d4 fb ff ff"):
        sys.exit("unrecognised SteamStub loader layout")
    header_dwords = u32(f, e + 0x1F)
    header = chained_xor(img.read(header_va, header_dwords * 4), u32(f, e + 0x3D))

    key = u32(header, H_PAYLOAD_KEY)
    payload = img.read(u32(header, H_PAYLOAD_VA), u32(header, H_PAYLOAD_SIZE))
    if u32(payload, 0) != key:
        sys.exit("payload is not decrypted in the file (needs Steam's handshake)")
    payload = chained_xor(payload, key, start=4)

    flags = u32(payload, P_FLAGS)
    code_va, code_size = u32(payload, P_CODE_VA), u32(payload, P_CODE_SIZE)
    oep = u32(payload, P_OEP)
    if not code_va <= oep < code_va + code_size:
        sys.exit("original entry point %#x outside the code (%#x+%#x): unknown "
                 "wrapper build" % (oep, code_va, code_size))
    if not flags & FLAG_NO_ENCRYPTION:
        enc = payload[P_STOLEN:P_STOLEN + 0x20] + img.read(code_va, code_size)
        plain = decrypt_code(payload[P_AES_KEY:P_AES_KEY + 0x20], enc)
        if len(plain) > code_size:
            sys.exit("decrypted code larger than its section")
        # The loader clears what the plaintext does not cover.
        plain += bytes(code_size - len(plain))
        o = img.off(code_va - img.base)
        f[o:o + code_size] = plain
    return oep, flags


def strip_bind(img):
    """Drop .bind (the loader, last section): nothing else refers to it."""
    name, va, vsize, raw_ptr, raw_size = img.sections[-1]
    if name != ".bind":
        sys.exit(".bind is not the last section")
    f = img.file
    for i in range(16):
        d = img.opt + 0x60 + i * 8
        rva, size = u32(f, d), u32(f, d + 4)
        if rva and size and va <= rva < va + vsize and i != 4:
            sys.exit("data directory %d points into .bind" % i)
    s = img.sec_table + (img.nsec - 1) * 0x28
    f[s:s + 0x28] = bytes(0x28)
    struct.pack_into("<H", f, img.pe + 6, img.nsec - 1)
    struct.pack_into("<I", f, img.opt + 0x38, va)  # SizeOfImage
    del f[raw_ptr:raw_ptr + raw_size]


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("exe")
    ap.add_argument("-o", "--output", required=True)
    args = ap.parse_args()
    with open(args.exe, "rb") as fh:
        img = Image(fh.read())
    oep, flags = unpack(img)
    struct.pack_into("<I", img.file, img.opt + 0x10, oep - img.base)
    struct.pack_into("<I", img.file, img.opt + 0x40, 0)  # CheckSum
    strip_bind(img)
    os.makedirs(os.path.dirname(os.path.abspath(args.output)), exist_ok=True)
    with open(args.output, "wb") as fh:
        fh.write(img.file)
    print("%s: entry %#x, flags %#x, %d bytes" % (args.output, oep, flags, len(img.file)))


if __name__ == "__main__":
    main()
