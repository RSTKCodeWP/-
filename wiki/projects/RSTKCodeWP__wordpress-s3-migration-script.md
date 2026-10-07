# WordPress S3 Migration Script

> Картка виставки. Зал: [Інше](../halls/other.md).

## Паспорт

| Поле | Значення |
|------|----------|
| Джерело | [RSTKCodeWP/wordpress-s3-migration-script](https://github.com/RSTKCodeWP/wordpress-s3-migration-script) |
| Локальна тека | `wordpress-s3-migration-script-WordPress-S3-Migration` |
| У бібліотеці | keep |
| Категорії каталогу | `other` |
| Зірки (каталог) | — |
| Оновлено upstream | — |
| Ліцензія (з файлу LICENSE або згадки) | GPL-2.0 |

## Ідея

Everything here assumes that you have already installed the plugin, added your S3 bucket, and are successfully able to upload NEW content to the S3 bucket. This is all standard functionality of the application, but if you're having trouble with it or haven't done it yet, [click here](http://premium.wpmudev.org/blog/moving-wordpress-media-to-amazon-s3/).

>aws s3 cp uploads/* s3://pnurkkala-test/wp-content/uploads/ --recursive

> php s3_upload.php

them from the local webserver to s3 for serving.

_З README.md, без переказу._

## Для чого

Everything here assumes that you have already installed the plugin, added your S3 bucket, and are successfully able to upload NEW content to the S3 bucket. This is all standard functionality of the application, but if you're having trouble with it or haven't done it yet, [click here](http://premium.wpmudev.org/blog/moving-wordpress-media-to-amazon-s3/).

_Окремого опису в каталозі немає. Це перший абзац README._

## Для кого

Аудиторія прямо не названа, і в описі немає маркерів (GCS, OSD, ELRS, прошивка, OpenIPC, KiCad).

## Функція

Окремого списку функцій у README немає.

## Як влаштовано

Корінь теки (без прихованих і без `node_modules` / `.git`):

- `LICENSE`
- `README.md`
- `s3_remove.php`
- `s3_upload.php`

Типи файлів за вибіркою (4 файлів, глибина до 3): .php (2), (без суфікса) (1), Markdown (1).


## Що треба

У джерелах цього репозиторію цього немає.

## Інструкція

Окремого розділу Install, Usage, Build або «Інструкція» в README немає. Команди запуску сюди не додавались.

## З чого зібрана картка

`catalog.json`, `wordpress-s3-migration-script-WordPress-S3-Migration/README.md`, маніфести збірки в корені теки, якщо вони є.

Сторінка: `wiki/projects/RSTKCodeWP__wordpress-s3-migration-script.md`.
