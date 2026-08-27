import { test, expect } from '@playwright/test'
import { findOrSeedClaim } from './claim-fixture'

// Must match playwright.config.ts's webServer ports.
const BACKEND_URL = 'http://127.0.0.1:8020'

/**
 * Regression test for a real bug the main journey test's own exploration
 * surfaced: the frontend used to hide "Analyze & Recommend" whenever ANY
 * recommendation existed for a claim, regardless of its status — so once a
 * recommendation was declined (or approved, or escalated), there was no way
 * to re-analyze that claim from the UI again, even though the backend
 * (Commander rule 3) only ever blocks a fresh run while one is genuinely
 * *pending*. Fixed in ClaimDetail.tsx: the re-analyze action now reappears
 * once a recommendation is resolved. This test is deliberately narrow — the
 * broad real-pipeline journey is human-review-journey.spec.ts's job.
 */
test('re-analyze reappears once a recommendation is resolved (declined)', async ({ page, request }) => {
  const claim = await findOrSeedClaim(request, BACKEND_URL)

  try {
    await page.goto(`/claims/${claim.claimId}`)

    const recommendationCard = page.locator('div').filter({ hasText: 'Recommended next step' }).last()

    // First recommendation: generate it, then decline it — the resolved
    // status this bug affected.
    await recommendationCard.getByRole('button', { name: /Analyze & Recommend/ }).click()
    await expect(recommendationCard.getByText('Pending', { exact: true })).toBeVisible({ timeout: 20_000 })

    const firstRec = await (await request.get(`${BACKEND_URL}/api/claims/${claim.claimId}/recommendation`)).json()
    const firstId = firstRec.recommendation.id as number

    await recommendationCard.getByRole('button', { name: 'Decline' }).click()
    await expect(recommendationCard.getByText('Declined', { exact: true })).toBeVisible({ timeout: 10_000 })

    // The bug: this button used to never reappear once any recommendation
    // (declined, approved, or escalated) existed for the claim.
    const reanalyzeButton = recommendationCard.getByRole('button', { name: /Re-analyze & Recommend/ })
    await expect(reanalyzeButton).toBeVisible({ timeout: 5_000 })

    // Clicking it must actually produce a fresh, genuinely pending
    // recommendation — not just redisplay the declined one.
    await reanalyzeButton.click()
    await expect(recommendationCard.getByText('Pending', { exact: true })).toBeVisible({ timeout: 20_000 })
    await expect(recommendationCard.getByText('Declined', { exact: true })).not.toBeVisible()

    // Confirm against the real API too, since the mock's canned rationale
    // text is identical every time and can't tell old vs. new apart: the
    // latest recommendation is a genuinely different, never-decided row —
    // not the declined one redisplayed.
    const secondRes = await request.get(`${BACKEND_URL}/api/claims/${claim.claimId}/recommendation`)
    const { recommendation } = (await secondRes.json()) as {
      recommendation: { id: number; approval_status: string; decided_at: string | null }
    }
    expect(recommendation.id).not.toBe(firstId)
    expect(recommendation.approval_status).toBe('pending')
    expect(recommendation.decided_at).toBeNull()
  } finally {
    await claim.cleanup()
  }
})
