
#AdditionalRequirementRules

AdditionalRequirementRule was updated to allow a rule to apply to
multiple modules.

Requirements:
- add a many-to-many relationship to Module
- relationship should support grouped module rules such as:
  "at least 9 credits across Methods and Statistics"

#Seed data

A management command "manage.py seed_demo_data" was added to aid efficient testing