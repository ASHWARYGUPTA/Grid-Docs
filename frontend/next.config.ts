import type { NextConfig } from "next";
import fs from "fs";
import path from "path";

// Programmatic rename script for user pasted screenshots
const publicDir = path.join(process.cwd(), "public");

const renameIfExists = (oldName: string, newName: string) => {
  const oldPath = path.join(publicDir, oldName);
  const newPath = path.join(publicDir, newName);
  if (fs.existsSync(oldPath)) {
    try {
      fs.renameSync(oldPath, newPath);
      console.log(`[NextConfig] Successfully renamed ${oldName} to ${newName}`);
    } catch (err) {
      console.error(`[NextConfig] Error renaming ${oldName}:`, err);
    }
  }
};

const copyIfExists = (srcName: string, destName: string) => {
  const srcPath = path.join(publicDir, srcName);
  const destPath = path.join(publicDir, destName);
  if (fs.existsSync(srcPath) && !fs.existsSync(destPath)) {
    try {
      fs.copyFileSync(srcPath, destPath);
      console.log(`[NextConfig] Successfully copied ${srcName} to ${destName}`);
    } catch (err) {
      console.error(`[NextConfig] Error copying ${srcName}:`, err);
    }
  }
};

renameIfExists("image.png", "live_monitor.png");
renameIfExists("image copy.png", "planned_events_wizard.png");
renameIfExists("image copy 2.png", "hotspots_analytics.png");
renameIfExists("image copy 3.png", "close_learn_dialog.png");

// Ensure fallback images exist
copyIfExists("close_learn_dialog.png", "live_monitor_transit.png");
copyIfExists("hotspots_analytics.png", "hotspots_analytics_detail.png");
copyIfExists("live_monitor.png", "governance_console.png");

const nextConfig: NextConfig = {
  /* config options here */
};

export default nextConfig;
