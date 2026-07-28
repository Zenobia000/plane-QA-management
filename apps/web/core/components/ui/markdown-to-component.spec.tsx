import { renderToStaticMarkup } from "react-dom/server";
import remarkGfm from "remark-gfm";
import { describe, expect, it } from "vitest";
import { MarkdownRenderer } from "./markdown-to-component";

describe("MarkdownRenderer", () => {
  it("renders QA evidence with CommonMark and GFM formatting", () => {
    const html = renderToStaticMarkup(
      <MarkdownRenderer
        markdown={"**Observed** `E_SETTLE`\n\n| Field | Value |\n| --- | --- |\n| Scope | vendor |"}
        options={{ remarkPlugins: [remarkGfm] }}
      />
    );

    expect(html).toContain("<strong>Observed</strong>");
    expect(html).toContain("<code>E_SETTLE</code>");
    expect(html).toContain("<table>");
    expect(html).toContain("vendor");
  });

  it("does not execute raw HTML from result notes", () => {
    const html = renderToStaticMarkup(<MarkdownRenderer markdown={'<script>alert("xss")</script>'} />);

    expect(html).not.toContain("<script>");
  });
});
