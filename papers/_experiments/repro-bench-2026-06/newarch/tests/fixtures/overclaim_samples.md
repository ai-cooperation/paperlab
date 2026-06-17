# Overclaim samples — Gate B fixture

> Known claim > evidence overclaims drawn from real review failures (ICS adversarial
> paper; SMC logic-audit; the claim<=evidence principle). Gate B must flag EACH listed
> overclaim below as a **P0**. The UNLISTED claim at the bottom is planted to test that
> independent claim extraction catches an overclaim that is *not* in this list.
>
> Format per sample: a fenced `claim` block + the grounded `evidence` it overstates.
> A claim is an overclaim when its quantifier / scope / certainty exceeds the evidence.

## S1 — fabricated experiment scale (ICS "1200 configs")

```claim
We evaluate our method across 1,200 distinct configurations, demonstrating robustness at scale.
```

```evidence
The experiment grid in the results table enumerates 24 configurations (4 models x 3 datasets x 2 seeds).
```

P0: claimed 1,200 vs 24 actually run — fabricated scale.

## S2 — quantifier inflation ("≥90%" when evidence is one run at 100%)

```claim
Our approach succeeds in at least 90% of cases across all benchmarks.
```

```evidence
A single benchmark run reports 100% success on 1 of the 3 benchmarks; the other two were not measured.
```

P0: "at least 90% across ALL benchmarks" generalises a single 100% run on one benchmark to all three.

## S3 — causal overreach from correlation

```claim
These results prove that increasing model size causes the observed accuracy gain.
```

```evidence
Accuracy and model size are positively correlated (r reported); no intervention / ablation isolates size.
```

P0: "prove ... causes" asserted from a correlation with no controlled manipulation.

## S4 — universal claim from bounded sample

```claim
The method always converges, regardless of initialization or learning rate.
```

```evidence
Convergence observed in the 5 training runs reported, all using the same optimizer and a fixed LR schedule.
```

P0: "always ... regardless of" is a universal claim; evidence is 5 runs under one fixed setting.

## S5 — clinical-strength language from feasibility-tier study

```claim
Clinicians should adopt this intervention as the first-line treatment.
```

```evidence
A constrained abstract-level pooled estimate emphasising direction and uncertainty, not definitive clinical guidance (per the contract's contribution statement).
```

P0: prescriptive first-line-treatment guidance exceeds a feasibility / direction-and-uncertainty study.

## UNLISTED (planted — not summarised above; independent extraction must still catch it)

```claim
State-of-the-art on every public leaderboard, outperforming all prior work by a wide margin.
```

```evidence
The comparison table includes 2 baselines on 1 dataset; "every public leaderboard" and "all prior work" are not evaluated.
```
