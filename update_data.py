name: Update Dosen Profile

on:
  schedule:
    - cron: '0 4 * * 1'   # setiap Senin jam 4 UTC
  workflow_dispatch:       # bisa dijalankan manual

jobs:
  build:
    runs-on: ubuntu-latest

    steps:
      - name: Checkout repo
        uses: actions/checkout@v4

      - name: Setup Python
        uses: actions/setup-python@v5
        with:
          python-version: '3.11'

      - name: Install dependencies
        run: |
          pip install requests beautifulsoup4 pddiktipy

      - name: Run script
        env:
          NAMA_DOSEN: "VICKY SETIA GUNAWAN"
          NAMA_PT:    "UNIVERSITAS PERINTIS INDONESIA"
          PRODI:      "BISNIS DIGITAL"
          SCHOLAR_ID: "zxh3WngAAAAJ"
        run: python update_profile.py

      - name: Upload artifact
        uses: actions/upload-artifact@v4
        with:
          name: dosen-profile
          path: data.json

      # Opsional: commit & push perubahan data.json
      - name: Commit updated data.json
        if: github.event_name != 'pull_request'
        run: |
          git config user.name "github-actions[bot]"
          git config user.email "github-actions[bot]@users.noreply.github.com"
          git add data.json
          git diff --staged --quiet || (git commit -m "Update profile data [skip ci]" && git push)
