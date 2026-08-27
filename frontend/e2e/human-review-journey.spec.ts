import { test, expect } from '@playwright/test'
import { findOrSeedClaim } from './claim-fixture'

// Must match playwright.config.ts's webServer ports.
const BACKEND_URL = 'http://127.0.0.1:8020'

/**
 * The one deliberately-specified critical journey, tying the whole real
 * pipeline together end to end through a real browser: real backend, real
 * Postgres, real Commander routing, real 01/04/05/06 agents. Only the
 * Claude API calls (02-reasoning-agent/03-recommendation-agent) are mocked
 * (MOCK_ANTHROPIC=1, see playwright.config.ts + backend/app/testing/
 * fake_anthropic.py) — for determinism and to avoid spending real tokens on
 * every test run, not because any other part of the system is faked.
 *
 * This is deliberately the only Playwright test in this project — broad UI
 * coverage is what the many focused backend unit/integration tests already
 * give us; this one proves the seam between all of them actually holds.
 */
test('critical journey: analyze, approve, real execution, and dashboard consistency', async ({ page, request }) => {
  const claim = await findOrSeedClaim(request, BACKEND_URL)

  try {
    // ---------------------------------------------------------------
    // Step 1 — "Login". This app has no real authentication yet (no
    // credential form, no session) — the only real affordance resembling a
    // login step is the homepage's "Sign in" link, which lands on the
    // Dashboard. Documented here rather than pretended around.
    // ---------------------------------------------------------------
    await page.goto('/')
    await page.getByRole('link', { name: 'Sign in' }).click()
    await expect(page).toHaveURL(/\/dashboard$/)

    // ---------------------------------------------------------------
    // Step 2 — Dashboard: the claim is High risk, so — being real,
    // Commander-scored data — it's one of the top-10 "Claims Needing
    // Attention" rows. Open it from there rather than typing its URL.
    // ---------------------------------------------------------------
    await expect(page.getByText('Claims Needing Attention')).toBeVisible()
    const dashboardRow = page.getByRole('row').filter({ hasText: claim.claimId })
    await expect(dashboardRow).toBeVisible({ timeout: 15_000 })
    const riskScoreBefore = await dashboardRow.locator('td').nth(4).innerText()
    await dashboardRow.click()
    await expect(page).toHaveURL(new RegExp(`/claims/${claim.claimId}$`))

    // ---------------------------------------------------------------
    // Step 3 — Claim Detail: run the real pipeline. 01-analyzer-agent runs
    // for real (deterministic rule engine, no mock); 02/03 are mocked for
    // determinism, but dispatched through the real Commander + real DB
    // writes exactly like every other trigger.
    // ---------------------------------------------------------------
    const analyzeButton = page.getByRole('button', { name: /Analyze & Recommend/ })
    await expect(analyzeButton).toBeVisible()
    await analyzeButton.click()

    const recommendationCard = page.locator('div').filter({ hasText: 'Recommended next step' }).last()
    await expect(recommendationCard.getByText('Pending', { exact: true })).toBeVisible({ timeout: 20_000 })

    // Verify the card actually shows action type, confidence, and rationale
    // — not just "something rendered".
    await expect(recommendationCard.getByText('Follow Up', { exact: true })).toBeVisible()
    await expect(recommendationCard.getByText('High confidence', { exact: true })).toBeVisible()
    await expect(recommendationCard.getByText(/An internal follow-up task is warranted for E2E testing/)).toBeVisible()

    // ---------------------------------------------------------------
    // Step 4 — Approve: real Commander rule 14 -> real 04-followup-agent
    // (or, for a payer_reminder recommendation, rule 15 -> 05; the fake LLM
    // output here is fixed to follow_up, but the assertions below don't
    // assume that — they read whatever the app actually reports).
    // ---------------------------------------------------------------
    await recommendationCard.getByRole('button', { name: 'Approve' }).click()

    // ---------------------------------------------------------------
    // Step 5 — outcome banner: branch on whatever genuinely happened
    // instead of assuming success.
    // ---------------------------------------------------------------
    const outcomeBanner = recommendationCard.getByText(/^Approved —/)
    await expect(outcomeBanner).toBeVisible({ timeout: 15_000 })
    const outcomeText = (await outcomeBanner.innerText()).trim()
    const realExecutionHappened = /follow-up created|reminder sent/.test(outcomeText)
    const wasEscalated = /escalated/.test(outcomeText)
    expect(realExecutionHappened || wasEscalated, `unexpected outcome banner text: "${outcomeText}"`).toBeTruthy()

    // ---------------------------------------------------------------
    // Step 6 — activity timeline reflects what actually happened, not a
    // generic "something happened" line.
    // ---------------------------------------------------------------
    await expect(page.getByText('Human Approved')).toBeVisible()
    if (realExecutionHappened) {
      await expect(page.getByText(/Followup Completed|Reminder Completed/)).toBeVisible()
    } else {
      await expect(page.getByText(/escalation #\d+/i)).toBeVisible()
    }

    // ---------------------------------------------------------------
    // Step 7 — back to Dashboard. Approving a follow_up/payer_reminder
    // recommendation never changes claims.status by design (04/05
    // explicitly never touch it — see docs/agents/04-followup-agent.md),
    // and the Dashboard table doesn't render a status column at all (only
    // risk_score/issue). So the meaningful check here is that the
    // Dashboard's live data for this claim still agrees with what Claim
    // Detail just showed — i.e. it's reading the same real row, not
    // something stale — rather than a literal status-badge transition.
    // ---------------------------------------------------------------
    await page.getByRole('link', { name: 'Dashboard' }).click()
    await expect(page).toHaveURL(/\/dashboard$/)
    const dashboardRowAfter = page.getByRole('row').filter({ hasText: claim.claimId })
    await expect(dashboardRowAfter).toBeVisible({ timeout: 15_000 })
    const riskScoreAfter = await dashboardRowAfter.locator('td').nth(4).innerText()
    expect(riskScoreAfter).toBe(riskScoreBefore)
  } finally {
    await claim.cleanup()
  }
})
