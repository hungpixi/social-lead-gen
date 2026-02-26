"""
Agent 1 — Avatar Checker.
So sánh hash ảnh đại diện để xác định ảnh thật hay mặc định.
Không dùng AI — chỉ dùng pixel hash (miễn phí 100%).
"""

import hashlib
import io
from loguru import logger

try:
    from PIL import Image
except ImportError:
    Image = None
    logger.warning("Pillow chưa cài. Chạy: pip install Pillow")


# Hash của các avatar mặc định phổ biến trên Facebook
# (sẽ cập nhật thêm khi chạy thực tế)
KNOWN_DEFAULT_HASHES = {
    # Facebook silhouette defaults — placeholder, cập nhật bằng cách
    # chạy compute_hash() trên các avatar mặc định thực tế
}


def compute_hash(image_bytes: bytes, size: tuple[int, int] = (32, 32)) -> str:
    """
    Tính perceptual hash của ảnh.
    Resize về 32x32 rồi hash MD5 để so sánh nhanh.
    """
    if not Image:
        return ""
    try:
        img = Image.open(io.BytesIO(image_bytes))
        img = img.convert("RGB").resize(size, Image.Resampling.LANCZOS)
        pixel_data = img.tobytes()
        return hashlib.md5(pixel_data).hexdigest()
    except Exception as e:
        logger.error(f"Hash error: {e}")
        return ""


def is_real_avatar(image_bytes: bytes) -> int:
    """
    Kiểm tra ảnh đại diện có phải ảnh thật không.
    Returns:
        1  = Ảnh thật (không match default)
        -1 = Ảnh mặc định
        0  = Không xác định được
    """
    if not image_bytes:
        return 0

    img_hash = compute_hash(image_bytes)
    if not img_hash:
        return 0

    if img_hash in KNOWN_DEFAULT_HASHES:
        return -1

    return 1


async def check_avatar_from_page(page, profile_url: str) -> int:
    """
    Tải avatar từ trang profile và kiểm tra.
    Dùng chung Playwright page để không tốn thêm tài nguyên.
    """
    try:
        # Lấy src của ảnh đại diện từ profile
        avatar_element = await page.query_selector(
            'svg[aria-label] image, '
            'image[preserveAspectRatio], '
            'img[data-imgperflogname="profileCoverPhoto"]'
        )
        if not avatar_element:
            return 0

        avatar_url = await avatar_element.get_attribute("xlink:href") or \
                     await avatar_element.get_attribute("src")

        if not avatar_url:
            return 0

        # Download ảnh
        response = await page.request.get(avatar_url)
        if response.status != 200:
            return 0

        image_bytes = await response.body()
        return is_real_avatar(image_bytes)

    except Exception as e:
        logger.debug(f"Avatar check failed for {profile_url}: {e}")
        return 0
