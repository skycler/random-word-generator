import io
import sys

import qrcode


def log_to_console(msg):
    print(msg, file=sys.stderr)


def make_qr_code(address):
    img = qrcode.make(address)
    img_io = io.BytesIO()
    img.save(img_io, "PNG", quality=60)
    img_io.seek(0)
    return img_io
