# Strategic Objective Mappings

## Overview

Strategic objectives evolve over time as the organization's vision changes. The workload analysis tool supports mapping historical strategic objectives to current ones for consistent reporting across years.

## Configuration

Add a `strategic_objective_mappings` section to your `team_mappings.yaml` file:

```yaml
strategic_objective_mappings:
  # Map old objectives to current ones
  "2025_increase_soc_conversion": "2026_scale_ecom"
  "2025_recurring_payments": "2026_recurring_payments"
  "2025_FR_DE_payments": "2026_fuel_regulated"

  # Keep current objectives as-is (identity mappings)
  "2026_fuel_regulated": "2026_fuel_regulated"
  "2026_scale_ecom": "2026_scale_ecom"
  "engineering_pillars": "engineering_pillars"
```

## How It Works

1. **Load Mappings**: The tool reads `strategic_objective_mappings` from `team_mappings.yaml`
2. **Apply Mapping**: When processing each initiative, the tool:
   - Gets the raw strategic objective from Jira
   - Looks it up in the mapping dictionary
   - Uses the mapped (current) objective if found
   - Falls back to the original value if no mapping exists
3. **Display**: The workload analysis CSV and reports show only the mapped (current) objectives

## Example Mappings

### Consolidating 2025 → 2026 Objectives

```yaml
strategic_objective_mappings:
  # eCommerce objectives
  "2025_increase_soc_conversion": "2026_scale_ecom"
  "2025_increase_soc_adoption": "2026_scale_ecom"
  "2024_2 Win eCommerce": "2026_scale_ecom"

  # Regulated markets
  "2025_FR_DE_payments": "2026_fuel_regulated"
  "2024_1 Scale iGaming and FS": "2026_fuel_regulated"

  # Network & infrastructure
  "2025_fraud_and_risk": "2026_network"
  "2025_scalability_and_reliability": "2026_network"

  # Recurring payments
  "2025_recurring_payments": "2026_recurring_payments"

  # Non-strategic / beyond strategic
  "2025_non_strategic_objective": "beyond_strategic"

  # Engineering foundations
  "2023_5_Optimise Operations": "engineering_pillars"
  "2024_4 Reach operating maturity": "engineering_pillars"
```

### Identity Mappings (Current Objectives)

Always include identity mappings for your current objectives to make the configuration explicit:

```yaml
strategic_objective_mappings:
  # Current 2026 objectives (no change)
  "2026_fuel_regulated": "2026_fuel_regulated"
  "2026_scale_ecom": "2026_scale_ecom"
  "2026_network": "2026_network"
  "2026_recurring_payments": "2026_recurring_payments"
  "engineering_pillars": "engineering_pillars"
  "beyond_strategic": "beyond_strategic"
```

## Benefits

1. **Consistent Reporting**: All initiatives use current strategic objective names
2. **Historical Data**: Old initiatives automatically align with new strategy
3. **Flexible**: Easy to update mappings as strategy evolves
4. **Transparent**: CSV shows the current objective, making analysis clearer

## Output Example

**Before Mapping:**
```csv
INIT-1029,"Merchant UI/UX guides","2025_increase_soc_conversion",DOCS,""
INIT-1170,"Payments Cancellation","2025_FR_DE_payments",PAYINS,"DOCS"
```

**After Mapping:**
```csv
INIT-1029,"Merchant UI/UX guides","2026_scale_ecom",DOCS,""
INIT-1170,"Payments Cancellation","2026_fuel_regulated",PAYINS,"DOCS"
```

## Maintenance

When your strategic objectives change:

1. Add new identity mappings for the new objectives
2. Map the previous year's objectives to current equivalents
3. Keep historical mappings (e.g., 2024 → 2026) for initiatives that haven't been updated

This ensures all initiatives, regardless of when they were created, align with your current strategic framework.
