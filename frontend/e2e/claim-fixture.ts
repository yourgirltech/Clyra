import type { APIRequestContext } from '@playwright/test'
import pg from 'pg'

const { Client } = pg

// Same Postgres this repo's backend/.env points at (DATABASE_URL) — real DB,
// not a throwaway test database, matching every other real-DB test in this
// project (backend/tests/test_escalation.py and friends).
const DB_CONFIG = {
  host: 'localhost',
  port: 5432,
  user: 'clyra',
  password: 'clyra',
  database: 'clyra',
}

const TERMINAL_STATUSES = new Set(['Paid', 'Denied', 'Rejected', 'Withdrawn', 'Closed'])

export type ClaimFixture = {
  claimId: string
  seeded: boolean
  cleanup: () => Promise<void>
}

/** Look for a real seeded High-risk, non-terminal claim with no recommendation
 * yet — the state the UI needs to show "Analyze & Recommend". Returns null
 * if the current seed data has none left (every one already has a
 * recommendation from a prior run/demo). */
async function findEligibleClaim(request: APIRequestContext, backendUrl: string): Promise<string | null> {
  const res = await request.get(`${backendUrl}/api/claims?risk_level=High&size=50&sort_by=risk_score&sort_dir=desc`)
  if (!res.ok()) return null
  const body = (await res.json()) as { items: Array<{ claim_id: string; status: string }> }
  for (const c of body.items) {
    if (TERMINAL_STATUSES.has(c.status)) continue
    const recRes = await request.get(`${backendUrl}/api/claims/${c.claim_id}/recommendation`)
    if (!recRes.ok()) continue
    const { recommendation } = (await recRes.json()) as { recommendation: unknown }
    if (recommendation === null) return c.claim_id
  }
  return null
}

/** Seed one fresh, minimal claim directly in Postgres when no eligible
 * seeded claim is left — two deterministic issues (missing_authorization +
 * code_mismatch, 50+30=80) guarantee real High risk once 01-analyzer-agent
 * actually runs on it, regardless of which payer we land on. */
async function seedFreshClaim(client: InstanceType<typeof Client>): Promise<string> {
  const clinic = await client.query('SELECT id FROM clinics ORDER BY id LIMIT 1')
  if (clinic.rows.length === 0) {
    throw new Error('No clinic found in the DB — run backend/scripts/seed_claims.py first')
  }
  const payer = await client.query('SELECT id FROM payers WHERE authorization_required = 1 ORDER BY id LIMIT 1')
  if (payer.rows.length === 0) {
    throw new Error('No payer with authorization_required=1 found — run backend/scripts/seed_claims.py first')
  }

  const claimId = `E2E-${Date.now()}`
  await client.query(
    `INSERT INTO claims
       (claim_id, clinic_id, payer_id, amount, status, risk_level, risk_score,
        authorization_present, documentation_present, coding_matches, last_followup_at, created_at, updated_at)
     VALUES ($1, $2, $3, $4, 'Submitted', 'High', 80, 0, 1, 0, now(), now(), now())`,
    [claimId, clinic.rows[0].id, payer.rows[0].id, 1234.56],
  )
  return claimId
}

async function wipeClaimDerivedRows(client: InstanceType<typeof Client>, claimId: string): Promise<void> {
  const claim = await client.query('SELECT id FROM claims WHERE claim_id = $1', [claimId])
  if (claim.rows.length === 0) return
  const claimPk = claim.rows[0].id
  await client.query('DELETE FROM activity_logs WHERE claim_id = $1', [claimPk])
  await client.query('DELETE FROM escalations WHERE claim_id = $1', [claimId])
  await client.query('DELETE FROM payer_reminders WHERE claim_id = $1', [claimPk])
  await client.query('DELETE FROM follow_ups WHERE claim_id = $1', [claimPk])
  await client.query('DELETE FROM recommendations WHERE claim_id = $1', [claimPk])
}

/** Find a real eligible seeded claim, or seed a fresh one if the pool is
 * exhausted — either way, `cleanup()` restores the DB to how it found it
 * (deletes everything this run created; for a found-not-seeded claim, that
 * means it's eligible again for the next run instead of being permanently
 * "used up"). Makes the journey test repeatable indefinitely without
 * depending on how much prior demo/test data already exists. */
export async function findOrSeedClaim(request: APIRequestContext, backendUrl: string): Promise<ClaimFixture> {
  const existing = await findEligibleClaim(request, backendUrl)
  if (existing) {
    return {
      claimId: existing,
      seeded: false,
      cleanup: async () => {
        const client = new Client(DB_CONFIG)
        await client.connect()
        try {
          await wipeClaimDerivedRows(client, existing)
        } finally {
          await client.end()
        }
      },
    }
  }

  const seedClient = new Client(DB_CONFIG)
  await seedClient.connect()
  let claimId: string
  try {
    claimId = await seedFreshClaim(seedClient)
  } finally {
    await seedClient.end()
  }

  return {
    claimId,
    seeded: true,
    cleanup: async () => {
      const client = new Client(DB_CONFIG)
      await client.connect()
      try {
        await wipeClaimDerivedRows(client, claimId)
        const claim = await client.query('SELECT id FROM claims WHERE claim_id = $1', [claimId])
        if (claim.rows.length > 0) {
          await client.query('DELETE FROM claim_issues WHERE claim_id = $1', [claim.rows[0].id])
        }
        await client.query('DELETE FROM claims WHERE claim_id = $1', [claimId])
      } finally {
        await client.end()
      }
    },
  }
}
