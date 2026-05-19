/** /docs/excel-upload-faq — Stub.
 *
 * 3.E.1 only ensures the route exists so the CRG13 actionable-hint link
 * doesn't 404. Real content expands in 3.E.6 / 3.E.9.
 */
import Link from "next/link";

export default function ExcelUploadFAQPage(): JSX.Element {
  return (
    <main className="mx-auto min-h-screen max-w-3xl px-6 py-12">
      <Link href="/console/excel" className="text-sm text-primary hover:underline">
        ← 返回 Excel 上传
      </Link>
      <h1 className="mt-4 text-3xl font-bold">Excel 上传常见问题</h1>
      <p className="mt-2 text-sm text-muted-foreground">
        Stub — 完整版随 3.E.6 / 3.E.9 上线
      </p>

      <article className="mt-8 space-y-6">
        <section>
          <h2 className="text-xl font-semibold">.xlsx 文件超过 5 MB 怎么办</h2>
          <p className="mt-2 text-sm">
            v1 上限为 5 MB。请尝试：
          </p>
          <ul className="ml-6 mt-2 list-disc space-y-1 text-sm text-muted-foreground">
            <li>删除只参考用的 sheet（保留参与求解的工作表）</li>
            <li>按客户 / 时间段 / 部门拆为 2 个 .xlsx</li>
            <li>导出为 .csv（≤10 MB，v1 末支持）</li>
          </ul>
        </section>

        <section>
          <h2 className="text-xl font-semibold">.xls (老格式) 不支持怎么办</h2>
          <p className="mt-2 text-sm">
            请在 Excel 中"另存为 .xlsx"再上传。.xls 是 Office 2003 之前的二进制格式，
            v1 不计划支持（解析复杂度高，覆盖率低）。
          </p>
        </section>

        <section>
          <h2 className="text-xl font-semibold">我的文件有图表 / 公式怎么办</h2>
          <p className="mt-2 text-sm">
            OptiCloud 只读取单元格的当前值（不重算公式、不解析图表）。
            如果某单元格依赖未求值的公式，请在 Excel 内按 F9 重算并保存后再上传。
          </p>
        </section>
      </article>
    </main>
  );
}
