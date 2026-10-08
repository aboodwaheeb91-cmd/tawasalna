# changelog.d — بند CHANGELOG لكل PR بملف لحاله (PR 3.11)

كل PR بيكتب بنده هون، **مش** بـ `docs/CHANGELOG.md` — هيك PRين مفتوحين ما بيتعارضوا أبداً على الـ CHANGELOG.

- اسم الملف: `<رقم-المهمة>.md` (مثال `3.11.md`).
- السطر الأول: `## PR <رقم-المهمة> — <عنوان> — YYYY-MM-DD` (الرقم = اسم الملف).
- بعده نقطة `- ` وحدة على الأقل.

`python tools/changelog_collect.py --check` بيتأكد من الشكل (بيشتغل بـ `run_tests.sh` على كل PR).
`python tools/changelog_collect.py` بينقلهم لـ `docs/CHANGELOG.md` (الأحدث فوق) وبيحذفهم — بيشتغل على main بعد الدمج، بـ commit لحاله.
