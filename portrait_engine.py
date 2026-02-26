import os

from PIL import Image
from PySide6.QtGui import QImage, QPixmap


class PortraitEngine:
    def __init__(self, sprites_dir: str):
        self._sprites_dir = sprites_dir
        self._png_cache: dict = {}

    def set_sprites_dir(self, path: str):
        self._sprites_dir = path
        self._png_cache = {}

    def clear_cache(self):
        self._png_cache = {}

    def build_layers(self, body, body_info, core, eye_base, eye_frame,
                     mouth_base, mouth_frame, use_rev, use_extra, use_blush) -> list:
        layers = [body]

        if eye_base and eye_frame:
            layers.append(f"{eye_base}_{eye_frame}")
        if mouth_base and mouth_frame:
            layers.append(f"{mouth_base}_{mouth_frame}")

        add_info = body_info.add_info
        if use_rev and add_info.get("addrev"):
            layers += add_info["addrev"]
        else:
            layers += add_info.get("add", [])

        if use_extra:
            layers += add_info.get("extras", [])
        if use_blush and body_info.has_blush:
            layers += add_info.get("cheek", [])

        return layers

    def render(self, layers, sprite_rects, canvas_rect, char_code, flip=False) -> QPixmap:
        img = self._composite(layers, sprite_rects, canvas_rect, char_code)
        if flip:
            img = img.transpose(Image.FLIP_LEFT_RIGHT)
        return self.pil_to_qpixmap(img)

    def _load_png(self, char_code: str, sprite_name: str):
        safe = sprite_name.replace("/", "_").replace("\\", "_").replace(" ", "_")
        path = os.path.join(self._sprites_dir, char_code, f"{safe}.png")
        if path in self._png_cache:
            return self._png_cache[path]
        if not os.path.exists(path):
            self._png_cache[path] = None
            return None
        img = Image.open(path).convert("RGBA")
        self._png_cache[path] = img
        return img

    def _composite(self, layers, sprite_rects, canvas_rect, char_code) -> Image.Image:
        cx, cy, cw, ch = canvas_rect
        cw = int(round(cw))
        ch = int(round(ch))
        canvas = Image.new("RGBA", (cw, ch), (0, 0, 0, 0))

        for name in layers:
            img = self._load_png(char_code, name)
            if img is None or name not in sprite_rects:
                continue
            rx, ry, rw, rh = sprite_rects[name]
            dl = int(round(rx - cx))
            dt = int(round(ch - (ry + rh - cy)))
            if dl < -img.width or dt < -img.height:
                continue
            canvas.alpha_composite(img, dest=(max(dl, 0), max(dt, 0)))

        return canvas

    @staticmethod
    def pil_to_qpixmap(img: Image.Image) -> QPixmap:
        data = img.tobytes("raw", "RGBA")
        qimg = QImage(data, img.width, img.height,
                      img.width * 4, QImage.Format.Format_RGBA8888)
        return QPixmap.fromImage(qimg)
