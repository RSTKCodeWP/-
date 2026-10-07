# OpenDrone Web

> Картка виставки. Зал: [Мости і ретранслятори](../halls/bridge.md).

## Паспорт

| Поле | Значення |
|------|----------|
| Джерело | [Just4Stan/OpenDrone-Web](https://github.com/Just4Stan/OpenDrone-Web) |
| Локальна тека | `fpv-library/repos/OpenDrone-Web-OpenDrone-webshop-Shopify-Hydrogen-or-Li` |
| У бібліотеці | skip |
| Категорії каталогу | `bridge` |
| Зірки (каталог) | 2 |
| Оновлено upstream | 2026-07-23 |
| Ліцензія (з файлу LICENSE або згадки) | MIT |

## Ідея

The storefront at **[opendrone.be](https://opendrone.be)**: open-source FPV drone hardware, designed and sold in Belgium: flight controllers (OpenFC), 4-in-1 ESCs (OpenESC), ExpressLRS receivers (OpenRX), and frames (OpenFrame), plus the OpenStack bundle.

It's a Shopify store under the hood, but not a themed one. This is a headless **Hydrogen** app on **Oxygen** (Shopify's Cloudflare Workers host): a `react-three-fiber` hero on the homepage, editorial product pages with scroll-revealed PCB teardowns, a trilingual legal system, and a stateless web↔Discord support desk that runs entirely inside the Worker. Shopify owns the cart, checkout, catalog, and customer accounts; this repo owns everything the buyer actually looks at.

Selling entity is **Incutec BV**; OpenDrone is the product brand. Storefront code is MIT; the hardware repos are CERN-OHL-S.

This README is the single source of trut…

_З README.md, без переказу._

## Для чого

OpenDrone webshop (Shopify Hydrogen or Liquid)

_Опис із каталогу бібліотеки (те, що було на GitHub на момент запису)._

## Для кого

Маркери в описі, темах і вступі (не здогадка понад текст):

- Розробник польотного контролера — у тексті є «flight controller».
- Інженер радіолінка — у тексті є «expresslrs».
- Майстерня обладнання — у тексті є «pcb».


Теми GitHub: `drone`, `ecommerce`, `fpv`, `hydrogen`, `open-source`, `react-router`, `shopify`, `storefront`, `tailwindcss`, `threejs`.

## Функція

Окремого списку функцій у README немає.

Єдине формулювання функції, яке є в каталозі: OpenDrone webshop (Shopify Hydrogen or Liquid)

## Як влаштовано

Корінь теки (без прихованих і без `node_modules` / `.git`):

- `app/`
- `brand/`
- `CLAUDE.md`
- `content/`
- `customer-accountapi.generated.d.ts`
- `docs/`
- `drafts/`
- `env.d.ts`
- `eslint.config.js`
- `LICENSE`
- `package-lock.json`
- `package.json`
- `public/`
- `react-router.config.ts`
- `README.md`
- `scripts/`
- `server.ts`
- `storefrontapi.generated.d.ts`
- `tsconfig.json`
- `vite.config.ts`

Типи файлів за вибіркою (497 файлів, глибина до 3): TypeScript (229), .svg (57), Markdown (50), .png (44), .mjs (37), JSON (24).


## Що треба

- Маніфести збірки: Node.js (package.json).
- npm-скрипти в package.json: `prebuild`, `build`, `dev`, `preview`, `lint`, `typecheck`, `test`, `codegen`, `check:registry`, `sync:legal`, `compose:newsletter`, `publish:post`.
- dependencies: `@formkit/auto-animate`, `@react-three/fiber`, `@react-three/postprocessing`, `@shopify/hydrogen`, `@tailwindcss/vite`, `graphql`, `isbot`, `lucide-react`, `motion`, `postprocessing`, `react`, `react-dom` і ще 3.

## Інструкція

Окремого розділу Install, Usage, Build або «Інструкція» в README немає. Команди запуску сюди не додавались.

## Супутні документи в теці

- [`docs/growth-architecture.md`](../../fpv-library/repos/OpenDrone-Web-OpenDrone-webshop-Shopify-Hydrogen-or-Li/docs/growth-architecture.md)
- [`docs/store-compliance.md`](../../fpv-library/repos/OpenDrone-Web-OpenDrone-webshop-Shopify-Hydrogen-or-Li/docs/store-compliance.md)

## З чого зібрана картка

`catalog.json`, `fpv-library/repos/OpenDrone-Web-OpenDrone-webshop-Shopify-Hydrogen-or-Li/README.md`, маніфести збірки в корені теки, якщо вони є.

Сторінка: `wiki/projects/Just4Stan__OpenDrone-Web.md`.
