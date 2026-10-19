import os


def read_emails(filename="email_500.txt"):
    # Файл из задания: одна строка = одно письмо.
    # Дополнительно понимаем формат from/text/date на трех строках.
    path = os.path.join(os.path.dirname(__file__), filename)
    emails = []
    current = {}

    with open(path, "r", encoding="utf-8-sig") as file:
        for raw_line in file:
            line = raw_line.strip()
            if not line:
                continue

            # Формат: from: ...: text: ...: date: ...
            if line.startswith("from:") and ": text:" in line and ": date:" in line:
                if current.get("sender") and current.get("text"):
                    emails.append(current)
                current = {}
                part1, part2 = line.split(": text:", 1)
                message, date = part2.rsplit(": date:", 1)
                sender = part1[5:].strip().rstrip(":")
                if sender and message.strip() and date.strip():
                    emails.append({
                        "sender": sender,
                        "text": message.strip(),
                        "date": date.strip()
                    })

            elif line.startswith("from:"):
                if current.get("sender") and current.get("text"):
                    emails.append(current)
                current = {"sender": line[5:].strip(), "text": "", "date": ""}

            elif line.startswith("text:"):
                current["text"] = line[5:].strip()

            elif line.startswith("date:"):
                current["date"] = line[5:].strip()
                if current.get("sender") and current.get("text"):
                    emails.append(current)
                current = {}

            elif current.get("text"):
                current["text"] += "\n" + line

    if current.get("sender") and current.get("text"):
        emails.append(current)

    return emails
