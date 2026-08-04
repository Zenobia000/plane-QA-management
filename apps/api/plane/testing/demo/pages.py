# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

"""The written record a delivery project accumulates, filed in a tree.

Pages was the one surface the seed left empty. That mattered twice over: a reader opening
Pages saw a blank list and could not tell whether the feature worked, and the Overview's
meeting-notes panel links straight here, so the war room pointed at nothing.

It also left the page hierarchy invisible. A folder in this product *is* a page with
children (ADR 0006), so a flat seed cannot show the feature at all -- nesting only appears
once something is nested. Three parents with children each is the smallest tree that
demonstrates it without inventing a filing system nobody asked for.

Content is written as `description_html` only. Page bodies are Yjs CRDT documents, and an
HTML-only write is safe exactly while a page has never been opened -- which is true of every
page this module creates, and stops being true the moment someone edits one. Do not reuse
this shortcut to update a page that already exists.
"""

from plane.db.models import Page, ProjectPage

# (folder, its blurb, [(child title, child body), ...])
#
# Deliberately tied to the rest of the seed -- the same sprints, the same Acme escalation
# the frontline panel carries -- so the demo reads as one project rather than six unrelated
# fixtures that happen to share a database.
TREE = (
    (
        "測試計畫",
        "這個專案的測試策略與各 sprint 的驗收範圍。每份計畫對應一個 cycle。",
        (
            (
                "2026-08A 回歸測試範圍",
                "<p>本 sprint 的回歸範圍以金流與訂單匯出為主。</p>"
                "<ul><li>金流：3DS challenge、退款、對帳回寫</li>"
                "<li>訂單匯出：5,000 筆以上的分批匯出（Acme 回報的逾時）</li>"
                "<li>權限：區域授權驗證</li></ul>"
                "<p>不在範圍：批次匯入的錯誤訊息改善，已排入 08B。</p>",
            ),
            (
                "金流模組測試策略",
                "<p>金流的驗收分三層：</p>"
                "<ol><li><strong>契約層</strong>：每條需求至少一條 happy path 與一條 unhappy path</li>"
                "<li><strong>整合層</strong>：與金流團隊的稽核回寫介面，目前被對方延後兩週擋住</li>"
                "<li><strong>法規層</strong>：稽核紀錄需保留一年，驗收證據不可刪改</li></ol>"
                "<p>第二層未通前，本模組不得標記為可發布。</p>",
            ),
        ),
    ),
    (
        "會議紀錄",
        "週會、回顧與客戶檢討的紀錄。決議寫在這裡，不寫在工作項的留言裡。",
        (
            (
                "2026-08-03 週會：Acme 匯出逾時升級 P1",
                "<p><strong>決議</strong>：Acme 月結匯出逾時升級為 P1。</p>"
                "<p>結帳窗口在月底前四天，若本週未修完會影響對方三個分公司。"
                "業務已先口頭致歉，修法與時程今日下班前回覆。</p>"
                "<p><strong>負責</strong>：後端組。<strong>追蹤</strong>：見公佈欄同日公告。</p>",
            ),
            (
                "2026-07-28 Sprint 2026-07B 回顧",
                "<p><strong>做得好</strong>：契約先行的做法讓兩條需求在實作前就補上了 unhappy path。</p>"
                "<p><strong>要改</strong>：跨團隊相依沒有在規劃時標出來，金流介面延後才發現，"
                "整條驗收鏈被擋住。下個 sprint 規劃時把外部相依列為必填。</p>"
                "<p><strong>帶走</strong>：一條故事延到 08A。</p>",
            ),
        ),
    ),
    (
        "發布",
        "每次出貨的說明與檢查清單。出貨判定看 Testing 的 release gate，不看這裡。",
        (
            (
                "上線前檢查清單",
                "<p>依序確認，任一項未過即不出貨：</p>"
                "<ol><li>release gate 為 ready（覆蓋率、最新一輪執行、未結缺陷三者皆通）</li>"
                "<li>法規稽核項目的驗收紀錄已歸檔</li>"
                "<li>對外承諾日已確認，或已與業務談過延期</li>"
                "<li>Intake 中標為已排入的客戶回報，本次有涵蓋的已在發布說明列出</li></ol>",
            ),
        ),
    ),
)


def create_pages(workspace, project, owner):
    """Three folders and their children, filed under the project.

    Returns the created folder pages so the caller can report what it built.
    """
    folders = []
    order = 0
    for folder_name, blurb, children in TREE:
        order += 1
        folder = _page(workspace, project, owner, folder_name, f"<p>{blurb}</p>", order * 1000)
        for index, (title, body) in enumerate(children, start=1):
            _page(workspace, project, owner, title, body, index * 1000, parent=folder)
        folders.append(folder)
    return folders


def _page(workspace, project, owner, name, html, sort_order, parent=None):
    page = Page.objects.create(
        workspace=workspace,
        name=name,
        description_html=html,
        # Powers search without opening the document. Crude tag-strip is enough here because
        # every body above is authored in this file and contains no attributes or entities.
        description_stripped=_strip(html),
        owned_by=owner,
        created_by=owner,
        access=Page.PUBLIC_ACCESS,
        parent=parent,
        sort_order=sort_order,
    )
    ProjectPage.objects.create(workspace=workspace, project=project, page=page, created_by=owner)
    return page


def _strip(html):
    out, inside = [], False
    for char in html:
        if char == "<":
            inside = True
        elif char == ">":
            inside = False
        elif not inside:
            out.append(char)
    return "".join(out).strip()
