# Kế Hoạch Cải Tiến UI/UX Frontend Quotify

## Trạng Thái

- Ngày lập kế hoạch: 22/08/2026.
- Người yêu cầu: nguyenvancuong@honghafeed.com.vn.
- Nguồn: 5 agent rà soát UI/UX chạy song song (phạm vi toàn bộ
  `frontend/src/pages/`, `frontend/src/layouts/AdminLayout.vue`, các SCSS
  partial liên quan), cộng với các lỗi layout đã xác minh trực tiếp bằng
  Playwright trong phiên làm việc trước (ví dụ bug input tràn cột ở
  `QuoteEditorPage.vue` do flex `min-width: auto`). Không phải toàn bộ phát
  hiện dưới đây đã được double-check bằng cách chạy app — những gì CHƯA
  verify trực tiếp được ghi rõ trong từng slice.
- Trạng thái: kế hoạch chưa triển khai, đang chờ duyệt trước khi tách thành
  các commit/slice riêng.

## Vấn Đề (Từ Góc Nhìn Người Dùng)

Sau nhiều phiên làm việc tập trung vào Dashboard, một số điểm không nhất
quán đã tích tụ giữa các trang khác của Quotify:

1. Một số class CSS kiểu Tailwind/PrimeFlex (`text-xs`, `font-bold`,
   `text-primary`, `bg-gray-50`, ...) được dùng trong template nhưng
   **không có tác dụng gì** vì dự án không cài Tailwind/PrimeFlex — hậu quả
   thực tế: giá trị quan trọng nhất trên `QuoteDetailPage`/`QuotesPage`
   ("Giá quy đổi VNĐ/KG") hiển thị không có nhấn mạnh nào dù code có ghi rõ ý
   định làm đậm/tô màu.
2. Hành động xoá không nhất quán về mức an toàn: có nơi xác nhận bằng Dialog
   đẹp, có nơi dùng `confirm()` gốc của trình duyệt (vỡ giao diện dark mode),
   có nơi xoá luôn không hỏi gì.
3. Nhiều bảng dữ liệu không có empty state riêng — khi lọc không ra kết quả,
   người dùng chỉ thấy tiêu đề cột trống hoặc dòng chữ tiếng Anh mặc định
   của PrimeVue, phá vỡ trải nghiệm toàn tiếng Việt.
4. Nút bị ẩn hoàn toàn khi thiếu quyền (thay vì disable + giải thích), khiến
   người dùng không phân biệt được "tính năng không tồn tại" và "tôi không
   có quyền".
5. Cùng 3 trạng thái báo giá (draft/confirmed/superseded) nhưng
   `QuoteDetailPage` và `QuotesPage` tô màu theo 2 cách khác nhau, không theo
   token ngữ nghĩa `--app-success`/`--app-warning` đã chuẩn hoá ở Dashboard.
6. Sidebar thu gọn làm mất hết nhãn chữ, không có tooltip thay thế — đúng lúc
   màn hình 1366px (loại máy đã từng gây bug thật) là nơi người dùng có xu
   hướng thu gọn sidebar nhất để lấy thêm không gian ngang.
7. Trang đăng nhập: lỗi không phải 401/network bị nuốt im lặng (submit chỉ
   dừng loading, không hiện gì); thông báo lỗi mạng lại gắn nhầm vào ô mật
   khẩu.

## Nguyên Tắc Chia Slice + TDD

- Mỗi slice độc lập, merge riêng được, không phá trạng thái build/test hiện
  tại của repo sau khi merge.
- Với mỗi slice có HÀNH VI kiểm thử được (empty state hiện đúng thông điệp,
  nút xác nhận gọi đúng action, class CSS đúng được gắn vào phần tử...): viết
  test trước ở trạng thái FAIL (mô tả đúng hành vi mong muốn), sau đó sửa
  code tới khi test PASS, cuối cùng dọn lại code nếu cần (refactor) mà không
  làm test đỏ lại. Dùng Vitest + `@vue/test-utils`, theo đúng pattern
  `mount(Component, { global: { stubs: {...} } })` với composable được mock
  qua `vi.mock(...)` — xem `frontend/tests/unit/dashboard.page.spec.ts` và
  `frontend/tests/unit/useDashboardPage.spec.ts` làm mẫu.
- Với thay đổi THUẦN THỊ GIÁC (đổi 1 class chết sang 1 class SCSS thật, đổi
  token màu) mà không có nhánh logic để test hành vi: vẫn viết 1 test khẳng
  định ĐÚNG CLASS/ĐÚNG CẤU TRÚC DOM mong muốn xuất hiện (ví dụ
  `wrapper.find('.quotes-page__price-value--converted').exists()`) thay vì
  bỏ qua kiểm thử — test này không xác minh màu sắc thực tế trên màn hình,
  nhưng khoá lại đúng class đang được dùng, tránh tái phát class chết. Việc
  xác minh thị giác cuối cùng (đúng màu, đúng độ đậm) làm thủ công qua
  Playwright hoặc trình duyệt thật, như đã làm với bug tràn cột
  `QuoteEditorPage.vue` trong phiên trước.
- Chạy `npm run typecheck` và bộ test liên quan (`npx vitest run
  <file(s) vừa sửa>`) sau mỗi slice trước khi coi là xong; chạy toàn bộ
  `npx vitest run` trước khi merge để bắt hồi quy chéo.

## Danh Sách Vấn Đề Đã Phát Hiện (Tham Chiếu Đầy Đủ)

### Nhóm A — Class CSS chết (Tailwind/PrimeFlex không tồn tại trong dự án)

- `QuoteDetailPage.vue`: dòng 106, 148, 225, 230, 231, 235, 240, 250, 269,
  270, 336, 430, 587, 589 — `text-xs`, `font-semibold`, `text-gray-400/500/
  700`, `border-round`, `mb-4`, `ml-4`, `mt-3`, `p-2`, `bg-gray-50`,
  `border-1 border-gray-200`, `max-h-20rem overflow-y-auto`. Quan trọng nhất:
  dòng 230, 240 — `font-bold text-primary` trên "Giá quy đổi (VNĐ/KG)".
- `QuotesPage.vue`: dòng 199, 205, 242 — `font-semibold`, và `font-bold
  text-primary` trên cùng giá trị "Giá quy đổi".
- `BackupsPage.vue`: dòng 43-44, 165-166, 403, 432 — `text-xl font-bold`,
  `text-sm text-muted`, `flex align-items-center gap-2`, `cursor-pointer
  select-none`, `text-danger`, `font-mono text-sm`, `white-space-pre-wrap p-2
  border-round surface-100 border-1 border-300 overflow-auto max-h-20rem`,
  `w-full mt-3`.
- `UsersPage.vue`: dòng 639 — `w-full mt-3`.

### Nhóm B — Hành động xoá/huỷ không nhất quán mức an toàn

- `QuoteEditorPage.vue:213` — `removeLine(index)` xoá ngay khi click, không
  xác nhận, chỉ phân biệt với nút nhân bản bằng icon + màu.
- `QuoteDetailPage.vue:831` — dùng `confirm()` gốc trình duyệt để xoá 1
  revision ghi chú, trong khi cùng file dùng Dialog PrimeVue có style riêng
  cho xoá draft/xác nhận version (dòng 506-541).
- `SuppliersPage.vue:490-498` (mẫu tương tự ở `useMaterialsPage.ts:228`,
  `useMaterialTypesPage.ts:209`) — dialog xác nhận xoá không cho biết trước
  bản ghi có đang được tham chiếu bởi báo giá nào không; người dùng chỉ biết
  sau khi bấm xác nhận và nhận lỗi 409. **Cần thêm API đếm số tham chiếu
  trước khi xoá — có phần backend, xem mục "Ngoài Phạm Vi".**

### Nhóm C — Thiếu empty state / loading state

- `QuotesPage.vue` — `DataTable` desktop (dòng 173) không có `#empty`
  template (bản mobile card đã có, dòng 355-359).
- `QuoteDetailPage.vue` — không có loading state nào khi `loadQuote(quoteId)`
  đang chạy (dòng 859).
- 4 trang danh mục (`MaterialsPage.vue`, `MaterialTypesPage.vue`,
  `SuppliersPage.vue`, và gián tiếp `QuotifySettingsPage.vue`) — không trang
  nào truyền `#empty` cho `DataTable`, rơi về text mặc định tiếng Anh của
  PrimeVue.

### Nhóm D — Quyền hạn ẩn control thay vì disable + giải thích

- `UsersPage.vue:33,42,51,127,136`, `RolesPage.vue:20,77,86`,
  `BackupsPage.vue:50,172,237,246` — dùng `v-if="permissionStore.can(...)"`
  để ẩn hẳn nút thay vì disable kèm tooltip.
- `RolesPage.vue:87` (xoá vai trò hệ thống) và `RolesPage.vue:205` (đổi tên
  vai trò hệ thống) — disable nhưng không có tooltip giải thích lý do.

### Nhóm E — Token màu trạng thái không nhất quán

- `QuoteDetailPage.vue` badge `.draft/.confirmed/.superseded` dùng
  `rgba(...)` cứng + `--orange-600`/`--green-600`; `QuotesPage.vue` badge
  `.status-draft/.status-confirmed/.status-superseded` dùng `color-mix()`
  với `--p-orange-500`/`--p-green-500`. Cả hai đều chưa dùng
  `--app-success`/`--app-warning` như Dashboard đã chuẩn hoá.
- `_quote-editor-page.scss:91-121` — banner backfill/error dùng `rgba(239,68,
  68,...)` + `var(--red-600, #dc2626)`, còn banner correction ngay bên dưới
  dùng đúng `color-mix(in srgb, var(--app-warning) ...)`.

### Nhóm F — Sidebar/Topbar/Trang đăng nhập (AdminLayout, LoginPage)

- `admin-layout.scss:416-450` — khi sidebar thu gọn, nhãn chữ `display:none`
  hoàn toàn, không có `title`/tooltip thay thế.
- `AdminLayout.vue:40-62` — không có "skip to content" link; bàn phím/trình
  đọc màn hình phải tab qua toàn bộ sidebar (5 nhóm) mới tới `<main>`.
- `admin-layout.scss:313-328,410-414` — `.admin-layout__profile-avatar-
  fallback` và `.admin-layout__footer-timezone` được style đầy đủ nhưng
  không còn template nào dùng tới (đã grep xác nhận).
- `AdminLayout.vue:13,69-73,87,322` — lẫn tiếng Anh (`Close menu`, `Expand/
  Collapse sidebar`, `Logout`) trong giao diện toàn tiếng Việt.
- `useLoginPage.ts:35-54` — chỉ xử lý `ApiError 401` và lỗi mạng
  (`TypeError`); lỗi khác (500, validation, timeout) `throw` không bắt, màn
  hình không hiện gì ngoài việc nút submit hết loading.
- `LoginPage.vue:47-49` / `useLoginPage.ts:44-48` — thông báo "Không thể kết
  nối tới dịch vụ xác thực" bị gắn vào slot lỗi của ô MẬT KHẨU, gây hiểu nhầm
  là sai mật khẩu.

### Nhóm G — Dashboard (mức độ nhẹ hơn, đã qua nhiều vòng polish)

- 3 chart có tính năng lệch nhau (crosshair + quick-range chỉ có ở chart kỳ
  hàng về; band-visibility + hover-info box chỉ có ở 2 chart so sánh) mà
  không có gì trong UI giải thích lý do khác biệt.
- Nhãn "(bắt buộc chọn)" trên `deliveryMonth`/`historyDeliveryMonth`/
  `seasonalMaterialId` xử lý validate/hiển thị khác nhau giữa 3 chart.

### Nhóm H — Rủi ro tràn ngang trên màn hình laptop 16:9 (~1366px)

- `SuppliersPage.vue:95-99` — cột "Vật tư cung cấp" nối tất cả tên vật tư
  bằng dấu phẩy vào 1 chuỗi, không giới hạn width/không truncate — có thể
  đẩy bảng tràn ngang trên NCC có nhiều vật tư, đúng loại bug 16:9 đã gặp
  thật ở `QuoteEditorPage.vue`.
- `_quote-editor-page.scss:144,160` — `min-width: 1100px` + `table-layout:
  fixed` đảm bảo không bóp méo cột (đã fix bug thật), nhưng đồng nghĩa MỌI
  màn hình hẹp hơn ~1100px cộng sidebar sẽ luôn phải cuộn ngang — chấp nhận
  được, chỉ ghi lại để không ai "sửa lại" table-layout theo hướng auto và tái
  phát bug cũ.

## Kế Hoạch Theo Từng Slice

### Slice 1 — Khôi phục nhấn mạnh "Giá quy đổi" (Nhóm A, phần quan trọng nhất)

- **Mục tiêu**: "Giá quy đổi (VNĐ/KG)" trên `QuoteDetailPage.vue` và
  `QuotesPage.vue` phải có class CSS THẬT làm đậm + tô màu accent, thay `font-
  bold text-primary` (chết) bằng 1 class BEM mới (ví dụ
  `quote-detail-page__price-highlight` / đã có sẵn
  `.quotes-page__price-value` — kiểm tra lại xem class đó có style thật
  chưa, nếu có thì chỉ cần bỏ 2 class chết).
- **File liên quan**: `QuoteDetailPage.vue` (dòng 230, 240),
  `_quote-detail-page.scss` (hoặc file SCSS tương ứng), `QuotesPage.vue`
  (dòng 242), `_quotes-page.scss`.
- **Test viết trước (đỏ)**: test mount `QuoteDetailPage`/`QuotesPage` (mock
  composable như các test hiện có), tìm phần tử hiển thị giá quy đổi, assert
  `classes()` KHÔNG chứa `font-bold`/`text-primary` (class chết) và CÓ chứa
  class BEM mới đã định nghĩa CSS thật (`getPropertyValue('font-weight')`
  qua `getComputedStyle` nếu môi trường jsdom load được SCSS đã compile —
  nếu jsdom không load CSS thật, chỉ assert đúng tên class, ghi rõ trong test
  rằng phần màu/độ đậm cần xác minh thủ công bằng trình duyệt).
- **Thay đổi code (xanh)**: sửa template + SCSS tới khi test pass.
- **Tiêu chí hoàn thành**: `npx vitest run` liên quan pass; mở trình duyệt
  (hoặc Playwright) xác nhận giá quy đổi in đậm + có màu accent ở cả light
  và dark mode.

### Slice 2 — Dọn các class chết còn lại (Nhóm A, phần còn lại)

- **Mục tiêu**: thay toàn bộ class Tailwind-style liệt kê ở Nhóm A (trừ phần
  đã xử lý ở Slice 1) bằng class SCSS thật hoặc token `--app-*` tương ứng ý
  định ban đầu (ví dụ `text-gray-500` → `color: var(--app-text-muted)`,
  `border-round border-1 border-gray-200` → border-radius + border token có
  sẵn).
- **File liên quan**: `QuoteDetailPage.vue` + SCSS của nó,
  `BackupsPage.vue` + `_backups-page.scss`, `UsersPage.vue:639`.
- **Test viết trước (đỏ)**: giống Slice 1 — assert đúng class BEM mới xuất
  hiện thay cho class chết, cho từng vị trí có nhánh hiển thị điều kiện
  (ví dụ khối lỗi JSON trong `BackupsPage.vue:430-435` chỉ hiện khi có lỗi —
  test phải trigger đúng state đó rồi assert class).
- **Thay đổi code (xanh)**: sửa template/SCSS.
- **Tiêu chí hoàn thành**: `grep` lại toàn bộ 4 file không còn class nằm
  trong danh sách Tailwind-style đã biết là chết; test pass; typecheck pass.

### Slice 3 — Empty state cho các bảng dữ liệu (Nhóm C)

- **Mục tiêu**: mọi `DataTable` chính (không phải bảng phụ trong dialog) có
  `#empty` template tiếng Việt, ngữ cảnh đúng loại dữ liệu (ví dụ "Không tìm
  thấy báo giá phù hợp với bộ lọc hiện tại.").
- **File liên quan**: `QuotesPage.vue`, `MaterialsPage.vue`,
  `MaterialTypesPage.vue`, `SuppliersPage.vue`.
- **Test viết trước (đỏ)**: với mỗi trang, mock composable trả về `items:
  []`/`isLoading: false`, mount component, assert text empty-state tiếng
  Việt cụ thể xuất hiện trong DOM (hiện tại sẽ fail vì không có `#empty`,
  PrimeVue render text mặc định hoặc rỗng).
- **Thay đổi code (xanh)**: thêm `#empty` template cho từng `DataTable`.
- **Tiêu chí hoàn thành**: 4 test mới (1 mỗi trang) pass; không còn `DataTable`
  chính nào thiếu `#empty` (`grep -L "#empty"` trong 4 file).

### Slice 4 — Loading state cho `QuoteDetailPage`

- **Mục tiêu**: hiện spinner/skeleton khi `loadQuote(quoteId)` đang chạy,
  thay vì màn hình trống.
- **File liên quan**: `QuoteDetailPage.vue`, composable liên quan (nếu có
  `isLoading` ref riêng, thêm nếu chưa có).
- **Test viết trước (đỏ)**: mock composable với `isLoading: true` (thêm ref
  mới nếu component chưa expose), mount, assert phần tử loading indicator
  (ví dụ `ProgressSpinner`/class `*-page__loading`) xuất hiện; case
  `isLoading: false` + có data thì loading indicator KHÔNG xuất hiện.
- **Thay đổi code (xanh)**: thêm `isLoading` ref (nếu thiếu) + `v-if` trong
  template.
- **Tiêu chí hoàn thành**: 2 test case (loading/loaded) pass.

### Slice 5 — Xác nhận trước khi xoá dòng vật tư trong `QuoteEditorPage`

- **Mục tiêu**: `removeLine(index)` phải hỏi xác nhận trước khi xoá (dùng
  cùng cơ chế Dialog đã có trong `QuoteDetailPage`, không dùng `confirm()`
  gốc).
- **File liên quan**: `QuoteEditorPage.vue:213` và composable tương ứng nếu
  logic xoá nằm ở đó.
- **Test viết trước (đỏ)**: mount editor với ≥1 dòng, click nút xoá, assert
  dòng CHƯA bị xoá khỏi `lines` cho tới khi Dialog xác nhận được bấm "Xoá";
  test case bấm "Huỷ" thì dòng vẫn còn nguyên.
- **Thay đổi code (xanh)**: thêm state `confirmingRemoveIndex`/Dialog, sửa
  `removeLine` chỉ xoá thật sau khi xác nhận.
- **Tiêu chí hoàn thành**: 2 test case (xác nhận xoá / huỷ) pass; hành vi
  nhân bản dòng (`duplicateLine`) không đổi (test hồi quy nếu có sẵn vẫn
  pass).

### Slice 6 — Thay `confirm()` gốc bằng Dialog cho xoá revision ghi chú

- **Mục tiêu**: `QuoteDetailPage.vue:831` dùng cùng pattern Dialog như xoá
  draft/xác nhận version trong cùng file, không dùng `window.confirm`.
- **File liên quan**: `QuoteDetailPage.vue`.
- **Test viết trước (đỏ)**: mount, trigger xoá 1 revision, assert
  KHÔNG gọi `window.confirm` (spy/mock global `confirm` phải không được gọi)
  và Dialog xác nhận riêng xuất hiện; xác nhận trong Dialog mới thực sự gọi
  action xoá.
- **Thay đổi code (xanh)**: thêm Dialog xác nhận riêng cho xoá revision,
  xoá lời gọi `confirm()`.
- **Tiêu chí hoàn thành**: test pass; `grep -n "confirm(" QuoteDetailPage.vue`
  không còn kết quả nào ngoài tên biến/hàm khác nghĩa.

### Slice 7 — Chuẩn hoá token màu badge trạng thái báo giá

- **Mục tiêu**: `QuoteDetailPage` và `QuotesPage` dùng CHUNG 1 bộ class/token
  cho 3 trạng thái draft/confirmed/superseded, theo `--app-success`/
  `--app-warning`/token trung tính tương ứng (không hard-code `rgba()`/
  `--orange-600`/`--p-orange-500`).
- **File liên quan**: SCSS của `QuoteDetailPage.vue` và `QuotesPage.vue`
  (cân nhắc tách ra 1 class dùng chung, ví dụ
  `frontend/src/styles/shared/_quote-status-badge.scss`, nếu quy ước dự án
  cho phép style dùng chung — kiểm tra `frontend/src/styles/` trước khi tạo
  file mới, ưu tiên tái sử dụng nếu đã có).
- **Test viết trước (đỏ)**: với mỗi trang, mount ở từng trạng thái
  (draft/confirmed/superseded), assert đúng class BEM mới được gắn (không
  assert giá trị màu thực tế qua jsdom).
- **Thay đổi code (xanh)**: đổi class + CSS.
- **Tiêu chí hoàn thành**: test pass; xác nhận thủ công màu nhất quán giữa 2
  trang, ở cả 2 theme.

### Slice 8 — Disable + tooltip thay vì ẩn control khi thiếu quyền

- **Mục tiêu**: các nút hiện đang `v-if="permissionStore.can(...)"` ở
  `UsersPage.vue`, `RolesPage.vue`, `BackupsPage.vue` (ít nhất các hành động
  update/delete) chuyển sang luôn render, `:disabled="!permissionStore.can(
  ...)"` kèm `v-tooltip`/`title` giải thích "Bạn không có quyền...".
- **File liên quan**: 3 file trên.
- **Test viết trước (đỏ)**: mock `permissionStore.can` trả `false`, mount,
  assert nút VẪN tồn tại trong DOM (`exists()` true) nhưng có thuộc tính
  `disabled`; assert có `title`/`aria-label` chứa nội dung giải thích quyền.
- **Thay đổi code (xanh)**: sửa `v-if` → `:disabled` + tooltip.
- **Tiêu chí hoàn thành**: test pass cho từng trang; test case
  `permissionStore.can` trả `true` vẫn cho phép click hoạt động bình thường
  (test hồi quy).

### Slice 9 — Tooltip cho nút disable vì lý do nghiệp vụ (vai trò hệ thống)

- **Mục tiêu**: `RolesPage.vue:87,205` (disable vì `isSystem`) có tooltip
  giải thích rõ lý do, không chỉ disable trơ.
- **File liên quan**: `RolesPage.vue`.
- **Test viết trước (đỏ)**: mount với 1 role `isSystem: true`, assert nút
  xoá/input tên có `title` chứa nội dung giải thích.
- **Thay đổi code (xanh)**: thêm `v-tooltip`/`title`.
- **Tiêu chí hoàn thành**: test pass.

### Slice 10 — Tooltip nhãn khi sidebar thu gọn

- **Mục tiêu**: khi sidebar ở trạng thái thu gọn, mỗi mục nav vẫn có
  `title`/tooltip hiện đúng tên mục.
- **File liên quan**: `AdminLayout.vue`, `admin-layout.scss:416-450`.
- **Test viết trước (đỏ)**: mount `AdminLayout` (hoặc component nav con nếu
  đã tách riêng) ở state collapsed, assert từng `<a>`/`<router-link>` nav có
  `title` bằng đúng tên mục.
- **Thay đổi code (xanh)**: thêm `:title="item.label"` (hoặc tương đương)
  vào từng nav item.
- **Tiêu chí hoàn thành**: test pass; xác nhận thủ công tooltip hiện khi hover
  ở trạng thái thu gọn.

### Slice 11 — Dọn dead CSS + đồng bộ ngôn ngữ trong AdminLayout

- **Mục tiêu**: xoá `.admin-layout__profile-avatar-fallback`,
  `.admin-layout__footer-timezone` (không còn dùng); dịch các chuỗi tiếng
  Anh còn sót (`Close menu`, `Expand/Collapse sidebar`, `Logout`) sang tiếng
  Việt nhất quán với phần còn lại.
- **File liên quan**: `admin-layout.scss`, `AdminLayout.vue`.
- **Test viết trước (đỏ)**: assert `aria-label`/text các nút liên quan bằng
  tiếng Việt đã chốt (ví dụ "Đóng menu", "Thu gọn/Mở rộng sidebar", "Đăng
  xuất") — test sẽ fail với text tiếng Anh hiện tại.
- **Thay đổi code (xanh)**: sửa text/aria-label; xoá 2 class CSS chết (xác
  nhận lại bằng `grep` trước khi xoá, đề phòng có nơi dùng ở template khác
  chưa rà).
- **Tiêu chí hoàn thành**: test pass; `grep` xác nhận 2 class đã xoá không
  còn ở đâu khác.

### Slice 12 — Xử lý lỗi đăng nhập đầy đủ + đúng vị trí

- **Mục tiêu**: mọi lỗi (không chỉ 401/network) khi đăng nhập đều hiện thông
  báo; lỗi mạng hiện ở banner cấp form, không gắn vào ô mật khẩu.
- **File liên quan**: `useLoginPage.ts:35-54`, `LoginPage.vue:47-49`.
- **Test viết trước (đỏ)**: test case lỗi 500 (hoặc lỗi generic khác) →
  assert có thông báo lỗi hiển thị (hiện tại sẽ fail vì bị `throw` không
  bắt); test case lỗi mạng → assert thông báo nằm ở vùng banner chung, KHÔNG
  nằm trong error-slot của input mật khẩu.
- **Thay đổi code (xanh)**: thêm `catch` mặc định trong `useLoginPage.ts`;
  tách state lỗi mạng ra khỏi state lỗi field mật khẩu; sửa template hiện
  banner riêng.
- **Tiêu chí hoàn thành**: 2 test case pass; test case 401 hiện có (nếu có)
  không bị ảnh hưởng.

### Slice 13 — Skip-to-content link

- **Mục tiêu**: có link "Bỏ qua đến nội dung" ẩn thị giác, hiện khi focus,
  trỏ tới `<main>`.
- **File liên quan**: `AdminLayout.vue`.
- **Test viết trước (đỏ)**: mount, assert tồn tại `<a href="#main-content">`
  (hoặc id tương ứng) là phần tử con gần như đầu tiên trong layout, trước
  `<nav>`.
- **Thay đổi code (xanh)**: thêm link + `id="main-content"` cho `<main>` +
  CSS ẩn-hiện-khi-focus (class `.sr-only`/`.visually-hidden` — kiểm tra đã
  có sẵn trong `primitives.scss` chưa trước khi thêm mới).
- **Tiêu chí hoàn thành**: test pass; test bằng bàn phím thủ công (Tab đầu
  tiên khi vào trang) xác nhận link hiện ra và nhảy đúng chỗ.

### Slice 14 — Bảo vệ tràn ngang cột "Vật tư cung cấp" (Suppliers)

- **Mục tiêu**: cột liệt kê vật tư trong `SuppliersPage.vue` không đẩy bảng
  tràn ngang trên NCC có nhiều vật tư — giới hạn width + ellipsis, chi tiết
  đầy đủ xem qua tooltip hoặc dialog.
- **File liên quan**: `SuppliersPage.vue:95-99`, SCSS tương ứng.
- **Test viết trước (đỏ)**: mount với 1 supplier có ví dụ 10 vật tư, assert
  phần tử hiển thị có class truncate (ví dụ `text-overflow: ellipsis` áp
  dụng qua class CSS) thay vì render toàn bộ chuỗi dài không giới hạn width
  — assert cụ thể: element có `max-width` set (kiểm tra style attribute nếu
  set inline, hoặc class có style thật) VÀ `title`/tooltip chứa đầy đủ danh
  sách.
- **Thay đổi code (xanh)**: thêm class giới hạn width + ellipsis + tooltip
  đầy đủ danh sách.
- **Tiêu chí hoàn thành**: test pass; xác nhận thủ công ở viewport 1366px
  không còn tràn ngang do riêng cột này.

### Slice 15 (tuỳ chọn, cần thảo luận thêm) — Đồng bộ tính năng giữa 3 chart Dashboard

- **Mục tiêu**: quyết định RÕ RÀNG (không phải code fix) — hoặc thêm
  crosshair/quick-range cho 2 chart so sánh, hoặc ghi chú trong UI vì sao 3
  chart khác nhau về tính năng. Đây là quyết định sản phẩm, cần chốt với
  người dùng trước khi viết code — KHÔNG bắt đầu bằng test vì chưa có hành
  vi mong muốn cụ thể để test.
- **Hành động ngay**: để slide này ở dạng "chờ quyết định", không lên kế
  hoạch chi tiết cho tới khi có câu trả lời.

## Thứ Tự Ưu Tiên Đề Xuất

1. Slice 1 (khôi phục nhấn mạnh giá quy đổi) — impact cao nhất, effort thấp.
2. Slice 5, 6 (an toàn thao tác xoá) — rủi ro mất dữ liệu do lỡ tay.
3. Slice 3, 4 (empty/loading state) — impact rộng, effort thấp-trung bình.
4. Slice 2 (dọn class chết còn lại) — effort thấp, dọn nợ kỹ thuật.
5. Slice 12 (lỗi đăng nhập) — impact cao vì là màn hình đầu tiên.
6. Slice 7 (token màu badge) — effort trung bình, cần quyết định class dùng
   chung ở đâu.
7. Slice 8, 9 (quyền hạn UI) — impact vừa, chỉ ảnh hưởng người dùng có phân
   quyền hạn chế.
8. Slice 10, 11, 13 (AdminLayout: tooltip, dead CSS, ngôn ngữ, skip-link) —
   gộp thành 1 đợt vì cùng file, effort thấp.
9. Slice 14 (tràn ngang Suppliers) — effort thấp, phòng ngừa bug tái phát.
10. Slice 15 — chờ quyết định sản phẩm, không tính vào lịch sửa code.

## Ngoài Phạm Vi (Của Kế Hoạch Frontend-Only Này)

- **Đếm số tham chiếu trước khi xoá NCC/vật tư/loại vật tư** (Nhóm B, mục
  `SuppliersPage.vue:490-498`) — cần thêm endpoint backend trả về số báo giá
  đang tham chiếu bản ghi trước khi cho xoá. Đây là thay đổi backend +
  frontend, cần 1 kế hoạch riêng (theo đúng quy ước `docs/quotify/plan-*.md`
  hiện có), không gộp vào đây.
- Quyết định sản phẩm ở Slice 15 (đồng bộ tính năng 3 chart Dashboard).
- `_quote-editor-page.scss` `min-width: 1100px` (Nhóm H, ý 2) — đã là quyết
  định kỹ thuật đúng cho bug đã fix, không cần sửa thêm, chỉ ghi lại để
  không ai vô tình revert.

## Ghi Chú Kiểm Thử

- Lệnh chạy test: `cd frontend && npx vitest run <path-tới-spec>` cho từng
  slice; `npx vitest run` (toàn bộ) trước khi merge slice cuối cùng của mỗi
  đợt.
- Lệnh typecheck: `cd frontend && npx vue-tsc --noEmit -p tsconfig.app.json`
  sau mỗi slice.
- Với các slice sửa SCSS: chạy thêm `cd frontend && npx vite build` (bỏ qua
  lỗi quyền ghi `dist/assets` nếu môi trường cục bộ gặp — đã biết là lỗi môi
  trường không liên quan tới nội dung sửa, xem lịch sử phiên làm việc) để
  xác nhận SCSS compile được trước khi coi slice hoàn thành.
- Test mount component theo đúng pattern đã dùng trong
  `frontend/tests/unit/dashboard.page.spec.ts` (mock composable qua
  `vi.mock`, stub các component PrimeVue nặng bằng `true`/passthrough).
- Sau khi mỗi slice merge và đã kiểm chứng, cập nhật
  `memory-bank/activeContext.md`/`memory-bank/progress.md` và ghi journal
  vào `.agent-memory/inbox/` theo `scripts/agent-task-close.sh`, đúng quy
  trình `AGENTS.md`.
