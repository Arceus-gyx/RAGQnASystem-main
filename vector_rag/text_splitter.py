def split_text(text, chunk_size=500, chunk_overlap=80):
    text = normalize_text(text)
    if not text:
        return []

    chunks = []
    start = 0
    text_len = len(text)
    while start < text_len:
        end = min(start + chunk_size, text_len)
        chunk = text[start:end].strip()
        if chunk:
            chunks.append(chunk)
        if end == text_len:
            break
        start = max(end - chunk_overlap, start + 1)
    return chunks


def normalize_text(text):
    lines = [line.strip() for line in text.replace("\r\n", "\n").split("\n")]
    lines = [line for line in lines if line]
    return "\n".join(lines)
