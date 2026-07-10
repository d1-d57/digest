import sys
from bs4 import BeautifulSoup
import re

ids = ["f6cc56ea8eebf912","b43ff409d6250efb","a3f398475fd85b78","94d3eea8d25c15a6",
"fb075975dc038484","6537d849be4a9276","f8c9d6896d3c8876","235c27c8db603aa6",
"97458d491f5e159b","9a5e2cf2914fe631","9d3bae6c0dd00e1a","ff5afec23a166789"]

for id_ in ids:
    with open(f"{id_}.html", encoding="utf-8", errors="ignore") as f:
        html = f.read()
    soup = BeautifulSoup(html, "html.parser")
    article = soup.find("article") or soup.find("div", class_=re.compile("entry-content|post-content"))
    if article is None:
        article = soup.find("div", id="content")
    text = article.get_text("\n", strip=True) if article else soup.get_text("\n", strip=True)
    with open(f"{id_}.txt", "w", encoding="utf-8") as f:
        f.write(text)
    print(id_, len(text))
