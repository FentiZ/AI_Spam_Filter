import json
from datetime import date

import ai
import database as db
from email_parser import read_emails
from prompts import PROMPTS


def title(text):
    print("\n" + "=" * 40)
    print(text.center(40))
    print("=" * 40)


def show_result(result):
    title("AI RESULT")
    print("Classification:", result["classification"].upper())
    print("Confidence:", str(round(result["confidence"] * 100, 1)) + "%")
    print("Risk:", result["risk"])
    print("Причины:")
    for reason in result["reasons"]:
        print(" -", reason)


def feedback(email_id, ai_classification):
    print("\nПравильная классификация?")
    print("1. Да")
    print("2. Нет, исправить")
    print("0. Пропустить")
    choice = input("Выбор: ").strip()

    if choice == "1":
        db.set_feedback(email_id, ai_classification)
        print("Оценка сохранена.")

    elif choice == "2":
        print("1. SPAM")
        print("2. NOT SPAM")
        answer = input("Правильный вариант: ").strip()
        if answer == "1":
            db.set_feedback(email_id, "spam")
            print("Исправление сохранено.")
        elif answer == "2":
            db.set_feedback(email_id, "not_spam")
            print("Исправление сохранено.")
        else:
            print("Изменение отменено.")


def check_one(version):
    title("ПРОВЕРКА EMAIL")
    sender = input("From: ").strip()
    if not sender:
        print("Отправитель не указан.")
        return

    print("Введите текст письма (пустая строка завершает ввод):")
    lines = []
    while True:
        line = input()
        if line == "":
            break
        lines.append(line)

    text = "\n".join(lines).strip()
    if not text:
        print("Пустое сообщение.")
        return

    today = date.today().isoformat()
    email_date = input("Дата (Enter = " + today + "): ").strip() or today

    try:
        result = ai.check_email(sender, text, version)
    except RuntimeError as error:
        print("Ошибка:", error)
        return

    email_id = db.save_email(sender, text, email_date, result, version)
    show_result(result)
    print("Сохранено в SQLite, ID:", email_id)
    feedback(email_id, result["classification"])


def analyze_file(version):
    title("АНАЛИЗ ФАЙЛА")
    try:
        emails = read_emails("email_500.txt")
    except OSError as error:
        print("Не удалось открыть email_500.txt:", error)
        return

    if not emails:
        print("В файле не найдено писем.")
        return

    print("Найдено писем:", len(emails))
    print("Вариант промпта:", version)
    print("Уже проверенные письма этой версии пропускаются.")
    print("Для быстрого теста можно сначала проверить 5 или 10 писем.")
    choice = input("Сколько проверить? (Enter = все): ").strip()
    if choice:
        try:
            count = int(choice)
            if count < 1:
                print("Нужно положительное число.")
                return
            emails = emails[:count]
        except ValueError:
            print("Некорректное число.")
            return

    spam = 0
    not_spam = 0
    new = 0
    skipped = 0
    failed = 0
    total_confidence = 0

    print("\nОбработка запущена. Ctrl+C — остановить.")
    try:
        for number, email in enumerate(emails, 1):
            key = db.make_key(email["sender"], email["text"], email["date"])
            existing = db.get_existing(key, version)

            if existing:
                classification = existing["ai_classification"]
                confidence = existing["confidence"]
                skipped += 1
            else:
                try:
                    result = ai.check_email(email["sender"], email["text"], version)
                    db.save_email(email["sender"], email["text"], email["date"], result, version)
                    classification = result["classification"]
                    confidence = result["confidence"]
                    new += 1
                except RuntimeError as error:
                    failed += 1
                    print("\nПисьмо", number, "- ошибка:", error)
                    if "Ollama" in str(error) or "подключиться" in str(error):
                        print("Останавливаю, проверь Ollama.")
                        break
                    continue

            if classification == "spam":
                spam += 1
            else:
                not_spam += 1
            total_confidence += confidence

            if number % 10 == 0 or number == len(emails):
                print("Обработано", number, "из", len(emails))

    except KeyboardInterrupt:
        print("\nАнализ прерван. Уже проверенные письма сохранены.")

    processed = spam + not_spam
    title("ANALYSIS REPORT")
    print("Processed:", processed)
    print("New:", new)
    print("Already in DB:", skipped)
    print("Errors:", failed)
    print("Spam:", spam)
    print("Not spam:", not_spam)
    if processed:
        print("Average confidence:", str(round(100 * total_confidence / processed, 1)) + "%")


def show_email(email_id):
    row = db.get_by_id(email_id)
    if not row:
        print("Письмо с таким ID не найдено.")
        return

    title("EMAIL " + str(row["id"]))
    print("From:", row["sender"])
    print("Date:", row["date"])
    print("Text:\n" + row["text"])
    print("\nAI:", row["ai_classification"].upper())
    print("User:", (row["user_classification"] or "нет оценки").upper())
    print("Confidence:", str(round(row["confidence"] * 100, 1)) + "%")
    print("Risk:", row["risk"])
    print("Prompt version:", row["prompt_version"])
    print("Причины:")
    for reason in json.loads(row["reasons"]):
        print(" -", reason)
    feedback(row["id"], row["ai_classification"])


def history(version):
    page = 0
    while True:
        title("ИСТОРИЯ (V" + str(version) + ")")
        rows = db.get_history(version, 15, page * 15)
        if not rows and page > 0:
            page -= 1
            continue
        if not rows:
            print("История пуста.")
            return

        for row in rows:
            print(
                "ID:", row["id"],
                "| From:", row["sender"],
                "| AI:", row["ai_classification"].upper(),
                "|", str(round(row["confidence"] * 100, 1)) + "%",
                "| User:", (row["user_classification"] or "-").upper()
            )
        print("\nВведите ID для просмотра и исправления.")
        print("N - следующая страница, P - предыдущая, 0 - назад")
        choice = input("Выбор: ").strip().lower()
        if choice == "0":
            return
        if choice == "n":
            page += 1
        elif choice == "p":
            page = max(0, page - 1)
        elif choice.isdigit():
            show_email(int(choice))
        else:
            print("Некорректный выбор.")


def statistics(version):
    rows = db.get_by_version(version)
    title("STATISTICS (V" + str(version) + ")")
    total = len(rows)
    spam = 0
    confidence = 0
    labeled = 0
    correct = 0
    wrong_spam = 0
    wrong_not_spam = 0

    for row in rows:
        if row["ai_classification"] == "spam":
            spam += 1
        confidence += row["confidence"]
        if row["user_classification"] is not None:
            labeled += 1
            if row["ai_classification"] == row["user_classification"]:
                correct += 1
            elif row["ai_classification"] == "spam":
                wrong_spam += 1
            else:
                wrong_not_spam += 1

    print("Total:", total)
    print("Spam:", spam)
    print("Not spam:", total - spam)
    if total:
        print("Average confidence:", str(round(100 * confidence / total, 1)) + "%")
    print("\nПисем с оценкой пользователя:", labeled)
    print("Correct:", correct)
    print("Incorrect:", labeled - correct)
    if labeled:
        print("Accuracy:", str(round(100 * correct / labeled, 1)) + "%")
    else:
        print("Accuracy: пока нельзя вычислить — нет feedback")
    print("\nAI SPAM -> User NOT SPAM:", wrong_spam)
    print("AI NOT SPAM -> User SPAM:", wrong_not_spam)
    print("Важно: точность рассчитывается только по письмам с feedback.")


def error_analysis():
    errors = db.get_errors()
    title("ОШИБКИ AI")
    if not errors:
        print("Пока нет ошибок с подтвержденной классификацией.")
        print("Добавь оценки в пункте 1 или через Историю.")
        return

    print("Ошибочных анализов (все версии):", len(errors))
    print("AI анализирует до 25 примеров за один запрос.")
    try:
        answer = ai.analyze_errors(errors)
        print("\n" + answer)
    except RuntimeError as error:
        print("Ошибка:", error)


def retest_labeled(version):
    rows = db.get_labeled_emails()
    if not rows:
        print("Нет писем с feedback. Сначала оцени несколько ответов AI.")
        return

    print("Писем с подтвержденной классификацией:", len(rows))
    print("Повторная проверка по V" + str(version) + " перезапишет результаты этой версии.")
    if input("Начать? (y/n): ").strip().lower() not in ("y", "yes", "д", "да"):
        return

    completed = 0
    try:
        for number, row in enumerate(rows, 1):
            try:
                result = ai.check_email(row["sender"], row["text"], version)
                db.save_email(row["sender"], row["text"], row["date"], result, version)
                completed += 1
                print("Проверено:", number, "/", len(rows))
            except RuntimeError as error:
                print("Ошибка:", error)
                if "Ollama" in str(error) or "подключиться" in str(error):
                    break
    except KeyboardInterrupt:
        print("\nОстановлено.")
    print("Успешно проверено:", completed)
    print("Теперь открой Статистику или Сравнение версий.")


def compare_versions():
    rows = db.get_all()
    versions = {}
    for row in rows:
        if row["user_classification"] is not None:
            version = row["prompt_version"]
            if version not in versions:
                versions[version] = {}
            versions[version][row["email_key"]] = row

    title("PROMPT COMPARISON")
    if not versions:
        print("Нет писем с feedback.")
        return

    # Сравниваем версии только на ОДНИХ И ТЕХ ЖЕ проверенных письмах.
    common_keys = None
    for version in versions:
        keys = set(versions[version].keys())
        if common_keys is None:
            common_keys = keys
        else:
            common_keys = common_keys.intersection(keys)

    if not common_keys:
        print("Нет общих размеченных писем между версиями.")
        return

    print("Общих проверенных писем:", len(common_keys))
    results = []
    for version in sorted(versions):
        correct = 0
        for key in common_keys:
            row = versions[version][key]
            if row["ai_classification"] == row["user_classification"]:
                correct += 1
        accuracy = 100 * correct / len(common_keys)
        results.append((accuracy, version))
        print("Version", version, "-> Accuracy:", str(round(accuracy, 1)) + "%")

    best = max(accuracy for accuracy, version in results)
    best_versions = [str(version) for accuracy, version in results if accuracy == best]
    print("Лучшая версия по этим письмам:", ", ".join(best_versions))


def prompt_menu(version):
    while True:
        title("PROMPT VERSIONS")
        print("Сейчас используется: V" + str(version))
        print("1. Выбрать V1 / V2 / V3")
        print("2. Повторно проверить письма с feedback")
        print("3. Сравнить версии")
        print("0. Назад")
        choice = input("Выбор: ").strip()

        if choice == "0":
            return version
        if choice == "1":
            print("Доступны версии:", ", ".join(str(v) for v in PROMPTS))
            answer = input("Номер версии: ").strip()
            if answer.isdigit() and int(answer) in PROMPTS:
                version = int(answer)
                print("Теперь активна V" + str(version))
            else:
                print("Такой версии нет.")
        elif choice == "2":
            retest_labeled(version)
        elif choice == "3":
            compare_versions()
        else:
            print("Некорректный выбор.")


def sender_statistics(version):
    rows = db.get_by_version(version)
    title("SENDERS (V" + str(version) + ")")
    if not rows:
        print("Данных нет.")
        return

    senders = {}
    domains = {}
    for row in rows:
        sender = row["sender"].lower()
        domain = sender.split("@")[-1]
        if sender not in senders:
            senders[sender] = [0, 0]
        if domain not in domains:
            domains[domain] = [0, 0]

        senders[sender][0] += 1
        domains[domain][0] += 1
        if row["ai_classification"] == "spam":
            senders[sender][1] += 1
            domains[domain][1] += 1

    print("\nПо доменам:")
    order = sorted(domains, key=lambda item: domains[item][0], reverse=True)
    for domain in order[:20]:
        print(domain, "| Emails:", domains[domain][0], "| Spam:", domains[domain][1])

    print("\nПо отдельным отправителям (первые 20):")
    order = sorted(senders, key=lambda item: senders[item][0], reverse=True)
    for sender in order[:20]:
        print(sender, "| Emails:", senders[sender][0], "| Spam:", senders[sender][1])


def main():
    db.init_db()
    version = 1
    while True:
        title("AI SPAM FILTER")
        print("Активный prompt: V" + str(version))
        print("1. Проверить email")
        print("2. Проанализировать файл email_500.txt")
        print("3. Посмотреть историю / исправить AI")
        print("4. Статистика")
        print("5. Проверить ошибки AI")
        print("6. Версии prompt / повторный тест")
        print("7. Статистика отправителей")
        print("0. Выход")

        choice = input("\nВыберите пункт: ").strip()
        if choice == "1":
            check_one(version)
        elif choice == "2":
            analyze_file(version)
        elif choice == "3":
            history(version)
        elif choice == "4":
            statistics(version)
        elif choice == "5":
            error_analysis()
        elif choice == "6":
            version = prompt_menu(version)
        elif choice == "7":
            sender_statistics(version)
        elif choice == "0":
            print("До свидания!")
            break
        else:
            print("Нет такого пункта.")


if __name__ == "__main__":
    try:
        main()
    except (KeyboardInterrupt, EOFError):
        print("\nПрограмма завершена.")
