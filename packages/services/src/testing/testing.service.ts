/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { API_BASE_URL } from "@plane/constants";
import type {
  TFileSignedURLResponse,
  TTestCase,
  TTestCaseAttachment,
  TTestCaseInput,
  TTestDefect,
  TTestDefectInput,
  TTestFolder,
  TTestResult,
  TTestResultAttachment,
  TTestResultInput,
  TReleaseEvidence,
  TReleaseEvidenceInput,
  TTestingCapabilities,
  TTestingOverview,
  TTestingRequirementCoverage,
  TTestingExportFormat,
  TTestingSearchResponse,
  TTestingSearchScope,
  TTestRun,
  TTestRunInput,
} from "@plane/types";
import { APIService } from "../api.service";
import { FileUploadService } from "../file/file-upload.service";
import { generateFileUploadPayload, getFileMetaDataForUpload } from "../file/helper";

type TTestCaseAttachmentUploadResponse = TFileSignedURLResponse & {
  attachment: TTestCaseAttachment;
};

export class TestingService extends APIService {
  private fileUploadService: FileUploadService;

  constructor(BASE_URL?: string) {
    super(BASE_URL || API_BASE_URL);
    this.fileUploadService = new FileUploadService();
  }

  private resultAttachmentsUrl(
    workspaceSlug: string,
    projectId: string,
    testRunId: string,
    runCaseId: string,
    resultId: string
  ) {
    return (
      `/api/workspaces/${workspaceSlug}/projects/${projectId}/testing/test-runs/${testRunId}` +
      `/cases/${runCaseId}/results/${resultId}/attachments/`
    );
  }

  async getResultAttachments(
    workspaceSlug: string,
    projectId: string,
    testRunId: string,
    runCaseId: string,
    resultId: string
  ): Promise<TTestResultAttachment[]> {
    return this.get(this.resultAttachmentsUrl(workspaceSlug, projectId, testRunId, runCaseId, resultId))
      .then((response) => response.data)
      .catch((error) => {
        throw error?.response?.data;
      });
  }

  /**
   * Four steps, the same as a work-item attachment: ask for a presigned target,
   * put the bytes there, then confirm so nothing is listed that never arrived.
   */
  async uploadResultAttachment(
    workspaceSlug: string,
    projectId: string,
    testRunId: string,
    runCaseId: string,
    resultId: string,
    file: File
  ): Promise<TTestResultAttachment> {
    const url = this.resultAttachmentsUrl(workspaceSlug, projectId, testRunId, runCaseId, resultId);
    const metadata = await getFileMetaDataForUpload(file);
    const response = await this.post(url, metadata).catch((error) => {
      throw error?.response?.data;
    });
    const signed = response.data;
    await this.fileUploadService.uploadFile(signed.upload_data.url, generateFileUploadPayload(signed, file));
    return this.patch(`${url}${signed.asset_id}/`)
      .then((confirmed) => confirmed.data)
      .catch((error) => {
        throw error?.response?.data;
      });
  }

  async deleteResultAttachment(
    workspaceSlug: string,
    projectId: string,
    testRunId: string,
    runCaseId: string,
    resultId: string,
    assetId: string
  ): Promise<void> {
    return this.delete(
      `${this.resultAttachmentsUrl(workspaceSlug, projectId, testRunId, runCaseId, resultId)}${assetId}/`
    )
      .then(() => undefined)
      .catch((error) => {
        throw error?.response?.data;
      });
  }

  async getCapabilities(workspaceSlug: string, projectId: string): Promise<TTestingCapabilities> {
    return this.get(`/api/workspaces/${workspaceSlug}/projects/${projectId}/testing/capabilities/`)
      .then((response) => response.data)
      .catch((error) => {
        throw error?.response?.data;
      });
  }

  async getOverview(workspaceSlug: string, projectId: string): Promise<TTestingOverview> {
    return this.get(`/api/workspaces/${workspaceSlug}/projects/${projectId}/testing/overview/`)
      .then((response) => response.data)
      .catch((error) => {
        throw error?.response?.data;
      });
  }

  async getReleaseEvidence(workspaceSlug: string, projectId: string): Promise<TReleaseEvidence[]> {
    return this.get(`/api/workspaces/${workspaceSlug}/projects/${projectId}/testing/release-evidence/`)
      .then((response) => response.data)
      .catch((error) => {
        throw error?.response?.data;
      });
  }

  async upsertReleaseEvidence(
    workspaceSlug: string,
    projectId: string,
    input: TReleaseEvidenceInput
  ): Promise<TReleaseEvidence> {
    return this.put(`/api/workspaces/${workspaceSlug}/projects/${projectId}/testing/release-evidence/`, input)
      .then((response) => response.data)
      .catch((error) => {
        throw error?.response?.data;
      });
  }

  async deleteReleaseEvidence(workspaceSlug: string, projectId: string, key: string): Promise<void> {
    return this.delete(`/api/workspaces/${workspaceSlug}/projects/${projectId}/testing/release-evidence/`, undefined, {
      params: { key },
    })
      .then(() => undefined)
      .catch((error) => {
        throw error?.response?.data;
      });
  }

  async getRequirementCoverage(workspaceSlug: string, projectId: string): Promise<TTestingRequirementCoverage> {
    return this.get(`/api/workspaces/${workspaceSlug}/projects/${projectId}/testing/requirement-coverage/`)
      .then((response) => response.data)
      .catch((error) => {
        throw error?.response?.data;
      });
  }

  async getFolders(workspaceSlug: string, projectId: string): Promise<TTestFolder[]> {
    return this.get(`/api/workspaces/${workspaceSlug}/projects/${projectId}/testing/folders/`)
      .then((response) => response.data)
      .catch((error) => {
        throw error?.response?.data;
      });
  }

  async createFolder(
    workspaceSlug: string,
    projectId: string,
    data: Pick<TTestFolder, "name"> & Partial<Pick<TTestFolder, "parent_id" | "sort_order">>
  ): Promise<TTestFolder> {
    return this.post(`/api/workspaces/${workspaceSlug}/projects/${projectId}/testing/folders/`, data)
      .then((response) => response.data)
      .catch((error) => {
        throw error?.response?.data;
      });
  }

  async updateFolder(
    workspaceSlug: string,
    projectId: string,
    folderId: string,
    data: Partial<Pick<TTestFolder, "name" | "parent_id" | "sort_order">>
  ): Promise<TTestFolder> {
    return this.patch(`/api/workspaces/${workspaceSlug}/projects/${projectId}/testing/folders/${folderId}/`, data)
      .then((response) => response.data)
      .catch((error) => {
        throw error?.response?.data;
      });
  }

  async deleteFolder(workspaceSlug: string, projectId: string, folderId: string): Promise<void> {
    return this.delete(`/api/workspaces/${workspaceSlug}/projects/${projectId}/testing/folders/${folderId}/`)
      .then(() => undefined)
      .catch((error) => {
        throw error?.response?.data;
      });
  }

  async exportLibraryCSV(workspaceSlug: string, projectId: string): Promise<string> {
    return this.get(`/api/workspaces/${workspaceSlug}/projects/${projectId}/testing/test-cases.csv`, {
      responseType: "text",
    })
      .then((response) => response.data)
      .catch((error) => {
        throw error?.response?.data;
      });
  }

  async importLibraryCSV(
    workspaceSlug: string,
    projectId: string,
    csvText: string
  ): Promise<{ created: number; diagnostics: Array<Record<string, unknown>>; case_ids: string[] }> {
    return this.post(`/api/workspaces/${workspaceSlug}/projects/${projectId}/testing/test-cases.csv`, {
      csv_text: csvText,
    })
      .then((response) => response.data)
      .catch((error) => {
        throw error?.response?.data;
      });
  }

  async getTestCases(workspaceSlug: string, projectId: string, search?: string): Promise<TTestCase[]> {
    return this.get(`/api/workspaces/${workspaceSlug}/projects/${projectId}/testing/test-cases/`, {
      params: search ? { search } : undefined,
    })
      .then((response) => response.data)
      .catch((error) => {
        throw error?.response?.data;
      });
  }

  async searchLibrary(
    workspaceSlug: string,
    projectId: string,
    query: string,
    scope: TTestingSearchScope = "all"
  ): Promise<TTestingSearchResponse> {
    return this.get(`/api/workspaces/${workspaceSlug}/projects/${projectId}/testing/search/`, {
      params: { query, scope },
    })
      .then((response) => response.data)
      .catch((error) => {
        throw error?.response?.data;
      });
  }

  async exportSearch(
    workspaceSlug: string,
    projectId: string,
    query: string,
    scope: TTestingSearchScope,
    format: TTestingExportFormat
  ): Promise<Blob> {
    return this.get(`/api/workspaces/${workspaceSlug}/projects/${projectId}/testing/export/`, {
      params: { query, scope, export_format: format },
      responseType: "blob",
    })
      .then((response) => response.data)
      .catch((error) => {
        throw error?.response?.data;
      });
  }

  async getTestCaseAttachments(
    workspaceSlug: string,
    projectId: string,
    testCaseId: string
  ): Promise<TTestCaseAttachment[]> {
    return this.get(
      `/api/workspaces/${workspaceSlug}/projects/${projectId}/testing/test-cases/${testCaseId}/attachments/`
    )
      .then((response) => response.data)
      .catch((error) => {
        throw error?.response?.data;
      });
  }

  async uploadTestCaseAttachment(
    workspaceSlug: string,
    projectId: string,
    testCaseId: string,
    file: File
  ): Promise<TTestCaseAttachment> {
    const detected = await getFileMetaDataForUpload(file);
    const fileMetadata = { ...detected, type: detected.type || file.type };
    const basePath = `/api/workspaces/${workspaceSlug}/projects/${projectId}/testing/test-cases/${testCaseId}/attachments`;
    return this.post(`${basePath}/`, fileMetadata)
      .then(async (response) => {
        const signed = response.data as TTestCaseAttachmentUploadResponse;
        await this.fileUploadService.uploadFile(signed.upload_data.url, generateFileUploadPayload(signed, file));
        await this.patch(`${basePath}/${signed.asset_id}/`);
        return signed.attachment;
      })
      .catch((error) => {
        throw error?.response?.data ?? error;
      });
  }

  async deleteTestCaseAttachment(
    workspaceSlug: string,
    projectId: string,
    testCaseId: string,
    attachmentId: string
  ): Promise<void> {
    return this.delete(
      `/api/workspaces/${workspaceSlug}/projects/${projectId}/testing/test-cases/${testCaseId}/attachments/${attachmentId}/`
    )
      .then(() => undefined)
      .catch((error) => {
        throw error?.response?.data;
      });
  }

  async getWorkItemTestCases(workspaceSlug: string, projectId: string, workItemId: string): Promise<TTestCase[]> {
    return this.get(`/api/workspaces/${workspaceSlug}/projects/${projectId}/testing/test-cases/`, {
      params: { work_item_id: workItemId },
    })
      .then((response) => response.data)
      .catch((error) => {
        throw error?.response?.data;
      });
  }

  async createTestCase(workspaceSlug: string, projectId: string, data: TTestCaseInput): Promise<TTestCase> {
    return this.post(`/api/workspaces/${workspaceSlug}/projects/${projectId}/testing/test-cases/`, data)
      .then((response) => response.data)
      .catch((error) => {
        throw error?.response?.data;
      });
  }

  async updateTestCase(
    workspaceSlug: string,
    projectId: string,
    testCaseId: string,
    data: Partial<TTestCaseInput>
  ): Promise<TTestCase> {
    return this.patch(`/api/workspaces/${workspaceSlug}/projects/${projectId}/testing/test-cases/${testCaseId}/`, data)
      .then((response) => response.data)
      .catch((error) => {
        throw error?.response?.data;
      });
  }

  async archiveTestCase(workspaceSlug: string, projectId: string, testCaseId: string): Promise<void> {
    return this.delete(`/api/workspaces/${workspaceSlug}/projects/${projectId}/testing/test-cases/${testCaseId}/`)
      .then(() => undefined)
      .catch((error) => {
        throw error?.response?.data;
      });
  }

  async unlinkWorkItem(workspaceSlug: string, projectId: string, testCaseId: string, issueId: string): Promise<void> {
    return this.delete(
      `/api/workspaces/${workspaceSlug}/projects/${projectId}/testing/test-cases/${testCaseId}/work-items/${issueId}/`
    )
      .then(() => undefined)
      .catch((error) => {
        throw error?.response?.data;
      });
  }

  async linkWorkItem(workspaceSlug: string, projectId: string, testCaseId: string, issueId: string): Promise<void> {
    return this.post(
      `/api/workspaces/${workspaceSlug}/projects/${projectId}/testing/test-cases/${testCaseId}/work-items/`,
      { issue_id: issueId }
    )
      .then(() => undefined)
      .catch((error) => {
        throw error?.response?.data;
      });
  }

  async getTestRuns(workspaceSlug: string, projectId: string): Promise<TTestRun[]> {
    return this.get(`/api/workspaces/${workspaceSlug}/projects/${projectId}/testing/test-runs/`)
      .then((response) => response.data)
      .catch((error) => {
        throw error?.response?.data;
      });
  }

  async createTestRun(workspaceSlug: string, projectId: string, data: TTestRunInput): Promise<TTestRun> {
    return this.post(`/api/workspaces/${workspaceSlug}/projects/${projectId}/testing/test-runs/`, data)
      .then((response) => response.data)
      .catch((error) => {
        throw error?.response?.data;
      });
  }

  async recordResult(
    workspaceSlug: string,
    projectId: string,
    testRunId: string,
    runCaseId: string,
    data: TTestResultInput
  ): Promise<TTestResult> {
    return this.post(
      `/api/workspaces/${workspaceSlug}/projects/${projectId}/testing/test-runs/${testRunId}/cases/${runCaseId}/results/`,
      data
    )
      .then((response) => response.data)
      .catch((error) => {
        throw error?.response?.data;
      });
  }

  async closeTestRun(workspaceSlug: string, projectId: string, testRunId: string): Promise<TTestRun> {
    return this.post(`/api/workspaces/${workspaceSlug}/projects/${projectId}/testing/test-runs/${testRunId}/close/`)
      .then((response) => response.data)
      .catch((error) => {
        throw error?.response?.data;
      });
  }

  async createDefect(
    workspaceSlug: string,
    projectId: string,
    testRunId: string,
    runCaseId: string,
    resultId: string,
    data: TTestDefectInput = {}
  ): Promise<TTestDefect> {
    return this.post(
      `/api/workspaces/${workspaceSlug}/projects/${projectId}/testing/test-runs/${testRunId}/cases/${runCaseId}/results/${resultId}/defects/`,
      data
    )
      .then((response) => response.data)
      .catch((error) => {
        throw error?.response?.data;
      });
  }
}
