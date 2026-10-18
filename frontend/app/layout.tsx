import type { Metadata } from "next";
import "./globals.css";
import { Providers } from "@/components/providers";
export const metadata: Metadata = {
  title: "赛探 AI · 发现你的下一场竞赛",
  description:
    "用智能浏览器搜索、整理和核验大学生竞赛信息。每一条结果，都有迹可循。",
};
export default function RootLayout({
  children,
}: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="zh-CN">
      <body>
        <Providers>{children}</Providers>
      </body>
    </html>
  );
}
