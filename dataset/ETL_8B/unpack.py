import codecs
import bitstring
from PIL import Image
from pathlib import Path
import argparse
import csv
import re
import jaconv
import numpy as np

char2class = [
    "あ",
    "い",
    "う",
    "え",
    "お",
    "か",
    "き",
    "く",
    "け",
    "こ",
    "さ",
    "し",
    "す",
    "せ",
    "そ",
    "た",
    "ち",
    "つ",
    "て",
    "と",
    "な",
    "に",
    "ぬ",
    "ね",
    "の",
    "は",
    "ひ",
    "ふ",
    "へ",
    "ほ",
    "ま",
    "み",
    "む",
    "め",
    "も",
    "や",
    "ゆ",
    "よ",
    "ら",
    "り",
    "る",
    "れ",
    "ろ",
    "わ",
    "ゐ",
    "ゑ",
    "を",
    "ん"
]

class CO59_to_utf8:
    def __init__(self, euc_co59_file='euc_co59.dat'):
        with codecs.open(euc_co59_file, 'r', 'euc-jp') as f:
            co59t = f.read()
        co59l = co59t.split()
        self.conv = {}
        for c in co59l:
            ch = c.split(':')
            co = ch[1].split(',')
            co59c = (int(co[0]), int(co[1]))
            self.conv[co59c] = ch[0]

    def __call__(self, co59):
        return self.conv[co59]

def T56(c):
    t56s = '0123456789[#@:>? ABCDEFGHI&.](<  JKLMNOPQR-$*);\'|/STUVWXYZ ,%="!'
    return t56s[c]

class ETLn_Record:
    def read(self, bs, pos=None):
        if pos:
            f.bytepos = pos * self.octets_per_record

        r = bs.readlist(self.bitstring)

        record = dict(zip(self.fields, r))

        self.record = {
            k: (self.converter[k](v) if k in self.converter else v)
            for k, v in record.items()
        }

        return self.record

    def get_image(self):
        return self.record['Image Data']

        
class ETL8G_Record(ETLn_Record):
    def __init__(self):
        self.octets_per_record = 8199
        self.fields = [
            "Serial Sheet Number", "JIS Kanji Code", "JIS Typical Reading", "Serial Data Number",
            "Evaluation of Individual Character Image", "Evaluation of Character Group",
            "Male-Female Code", "Age of Writer",
            "Industry Classification Code", "Occupation Classification Code",
            "Sheet Gatherring Date", "Scanning Date",
            "Sample Position X on Sheet", "Sample Position Y on Sheet", "Image Data"
        ]
        self.bitstring = 'uint:16,hex:16,bytes:8,uint:32,4*uint:8,4*uint:16,2*uint:8,pad:240,bytes:8128,pad:88'
        self.converter = {
            'JIS Typical Reading': lambda x: x.decode('ascii'),
            'Image Data': lambda x: Image.eval(Image.frombytes('F', (128, 127), x, 'bit', 4).convert('L'),
            lambda x: x * 16)
        }
    
    def get_char(self):
        char = bytes.fromhex(
            '1b2442' + self.record['JIS Kanji Code'] + '1b2842').decode('iso2022_jp')
        return char

class ETL8B_Record(ETLn_Record):
    def __init__(self):
        self.octets_per_record = 512
        self.fields = [
            "Serial Sheet Number", "JIS Kanji Code", "JIS Typical Reading", "Image Data"
        ]
        self.bitstring = 'uint:16,hex:16,bytes:4,bytes:504'
        self.converter = {
            'JIS Typical Reading': lambda x: x.decode('ascii'),
            'Image Data': lambda x: Image.frombytes('1', (64, 63), x, 'raw')
        }

    def get_char(self):
        char = bytes.fromhex(
            '1b2442' + self.record['JIS Kanji Code'] + '1b2842').decode('iso2022_jp')
        return char

def unpack(filename, etln_record):

    base = Path(filename).name
    folder = Path(filename).parent

    f = bitstring.ConstBitStream(filename=filename)

    if re.match(r'ETL[89]B_Record', etln_record.__class__.__name__):
        f.bytepos = etln_record.octets_per_record

    chars = []
    images = []
    records = []

    rows, cols = 40, 50
    rows_by_cols = rows * cols

    c = 0
    hiragana_rows = []
    while f.pos < f.length:

        record = etln_record.read(f)
        char = etln_record.get_char()
        img = etln_record.get_image()

        chars.append(char)
        images.append(img)
        records.append(record)

        if (char in char2class):
            print(char, end=',')
            idx = char2class.index(char)
            img = img.resize((32,32))
            np_img = np.asarray(img, dtype=np.ubyte)
            list_img = np_img.flatten().tolist()
            assert len(list_img) == 32*32

            hiragana_rows.append(([idx] + list_img))

    csvfn = folder / '{}.csv'.format(base)

    with open(csvfn, 'w', encoding="utf-8", newline='') as f:
        writer = csv.writer(f)
        writer.writerows(hiragana_rows)

if __name__ == '__main__':

    parser = argparse.ArgumentParser(description='Decompose ETLn files')
    parser.add_argument('input', help='input files')

    args = parser.parse_args()

    base = Path(args.input).name

    if re.match(r'ETL[167]', base):
        etln_record = ETL167_Record()
    elif re.match(r'ETL2', base):
        etln_record = ETL2_Record()
    elif re.match(r'ETL[345]', base):
        etln_record = ETL345_Record()
    elif re.match(r'ETL8G', base):
        etln_record = ETL8G_Record()
    elif re.match(r'ETL8B', base):
        etln_record = ETL8B_Record()
    elif re.match(r'ETL9G', base):
        etln_record = ETL9G_Record()
    elif re.match(r'ETL9B', base):
        etln_record = ETL9B_Record()

    unpack(args.input, etln_record)
