
    # Image reports
    image_dir = Path("IN_image")
    if image_dir.exists():
        for file in sorted(image_dir.glob("*.txt")):
            reports_data['image_reports'].append({
                'name': file.name,
              