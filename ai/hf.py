import os, time, requests

HF_TOKEN = os.getenv("HF_TOKEN")
HF_TEXT_MODEL = os.getenv("HF_TEXT_MODEL")
HF_IMAGE_MODEL = os.getenv("HF_IMAGE_MODEL", "nateraw/food")

class HFError(Exception):
    pass

def hf_text2text(prompt: str, max_new_tokens: int = 180, retries: int = 2) -> str:
    """
    허깅페이스 Hosted Inference API로 텍스트 생성.
    - 콜드스타트(503)면 짧게 재시도.
    """
    if not HF_TOKEN:
        raise HFError("HF_TOKEN not set")
    if not HF_TEXT_MODEL:
        raise HFError("HF_TEXT_MODEL not set in .env file")

    # 환경 변수에 전체 URL이 있어도, 모델 ID만 있어도 모두 처리
    if HF_TEXT_MODEL.startswith("https://"):
        url = HF_TEXT_MODEL
    else:
        url = f"https://api-inference.huggingface.co/models/{HF_TEXT_MODEL}"
    headers = {"Authorization": f"Bearer {HF_TOKEN}"}
    payload = {
        "inputs": prompt,
        "parameters": {"max_new_tokens": max_new_tokens},
        "options": {"wait_for_model": True}  # 모델 깨우기
    }

    for i in range(retries + 1):
        r = requests.post(url, headers=headers, json=payload, timeout=60)
        if r.status_code == 503:
            # 모델 로딩 중 → 잠깐 기다렸다가 재시도
            time.sleep(2 + i)
            continue
        if not r.ok:
            raise HFError(f"HF API error {r.status_code}: {r.text}")

        data = r.json()
        # 다양한 응답 포맷 처리
        if isinstance(data, list) and data and "generated_text" in data[0]:
            return data[0]["generated_text"]
        elif isinstance(data, dict) and "generated_text" in data:
            return data["generated_text"]
        raise HFError(f"Unexpected API response format: {data}")

    raise HFError("HF API not ready after retries")


def hf_image_classify(image_bytes: bytes, top_k: int = 3, retries: int = 2):
    """허깅페이스 이미지 분류 API 호출."""
    if not HF_TOKEN:
        raise HFError("HF_TOKEN not set")
    if not HF_IMAGE_MODEL: # pragma: no cover
        raise HFError("HF_IMAGE_MODEL not set in .env file")

    # 환경 변수에 전체 URL이 있어도, 모델 ID만 있어도 모두 처리
    if HF_IMAGE_MODEL.startswith("https://"):
        url = HF_IMAGE_MODEL
    else:
        url = f"https://api-inference.huggingface.co/models/{HF_IMAGE_MODEL}"
    headers = {
        "Authorization": f"Bearer {HF_TOKEN}",
        "Accept": "application/json",
        "Content-Type": "application/octet-stream",
    }

    for i in range(retries + 1):
        r = requests.post(
            url,
            headers=headers,
            params={"wait_for_model": "true"},
            data=image_bytes,
            timeout=60,
        )
        if r.status_code == 503:
            time.sleep(2 + i)
            continue
        if not r.ok:
            raise HFError(f"HF API error {r.status_code}: {r.text}")

        data = r.json()
        if isinstance(data, list):
            predictions = []
            for item in data[:top_k]:
                label = item.get("label") or item.get("class")
                score = item.get("score") or item.get("confidence", 0)
                if label is None:
                    continue
                predictions.append({"label": label, "score": float(score or 0)})
            if predictions:
                return predictions
        # 응답이 리스트가 아니면 (e.g. {"error": "Model is loading"})
        # 잠시 기다렸다가 재시도합니다.
        time.sleep(1)
        time.sleep(1 + i)

    raise HFError("HF API not ready after retries")
