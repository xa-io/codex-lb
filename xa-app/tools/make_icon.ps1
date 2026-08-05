# Generates the deterministic XA-style LB application icon.
$ErrorActionPreference = 'Stop'
Add-Type -AssemblyName System.Drawing

Add-Type -ReferencedAssemblies System.Drawing -TypeDefinition @'
using System;
using System.Drawing;
using System.Drawing.Imaging;
using System.Runtime.InteropServices;
public static class CodexLbInkScan {
    public static int[] Box(Bitmap bitmap, int alphaMin) {
        Rectangle rect = new Rectangle(0, 0, bitmap.Width, bitmap.Height);
        BitmapData data = bitmap.LockBits(rect, ImageLockMode.ReadOnly, PixelFormat.Format32bppArgb);
        int minX = int.MaxValue, maxX = -1, minY = int.MaxValue, maxY = -1;
        byte[] row = new byte[data.Stride];
        for (int y = 0; y < bitmap.Height; y++) {
            Marshal.Copy(IntPtr.Add(data.Scan0, y * data.Stride), row, 0, data.Stride);
            for (int x = 0; x < bitmap.Width; x++) {
                if (row[x * 4 + 3] < alphaMin) continue;
                if (x < minX) minX = x;
                if (x > maxX) maxX = x;
                if (y < minY) minY = y;
                if (y > maxY) maxY = y;
            }
        }
        bitmap.UnlockBits(data);
        return new int[] { minX, minY, maxX, maxY };
    }
}
'@

$out = [System.IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..\resources\codex-lb.ico'))

function New-RoundRect([single]$x, [single]$y, [single]$w, [single]$h, [single]$r) {
    $path = New-Object System.Drawing.Drawing2D.GraphicsPath
    $diameter = 2 * $r
    $path.AddArc($x, $y, $diameter, $diameter, 180, 90)
    $path.AddArc($x + $w - $diameter, $y, $diameter, $diameter, 270, 90)
    $path.AddArc($x + $w - $diameter, $y + $h - $diameter, $diameter, $diameter, 0, 90)
    $path.AddArc($x, $y + $h - $diameter, $diameter, $diameter, 90, 90)
    $path.CloseFigure()
    return $path
}

$backgroundTop = [System.Drawing.Color]::FromArgb(255, 0x22, 0x2f, 0x4a)
$backgroundBottom = [System.Drawing.Color]::FromArgb(255, 0x0d, 0x11, 0x17)
$accent = [System.Drawing.Color]::FromArgb(255, 0x4f, 0x8f, 0xf7)
$white = [System.Drawing.Color]::FromArgb(255, 0xe8, 0xed, 0xf5)
$sizes = 256, 128, 64, 48, 32, 24, 16
$entries = @()

foreach ($size in $sizes) {
    $bitmap = New-Object System.Drawing.Bitmap($size, $size)
    $graphics = [System.Drawing.Graphics]::FromImage($bitmap)
    $graphics.SmoothingMode = [System.Drawing.Drawing2D.SmoothingMode]::AntiAlias
    $graphics.TextRenderingHint = [System.Drawing.Text.TextRenderingHint]::AntiAliasGridFit
    $graphics.Clear([System.Drawing.Color]::Transparent)

    $scale = $size / 256.0
    $inset = [Math]::Max(1.0, 6.0 * $scale)
    $width = $size - 2 * $inset
    $radius = [Math]::Max(2.0, 46.0 * $scale)
    $path = New-RoundRect $inset $inset $width $width $radius
    $rect = New-Object System.Drawing.RectangleF(0, 0, $size, $size)
    $brush = New-Object System.Drawing.Drawing2D.LinearGradientBrush($rect, $backgroundTop, $backgroundBottom, 65.0)
    $graphics.FillPath($brush, $path)

    if ($size -ge 32) {
        $penWidth = [Math]::Max(2.0, 11.0 * $scale)
        $pen = New-Object System.Drawing.Pen($accent, $penWidth)
        $borderInset = $inset + $penWidth / 2.0
        $borderPath = New-RoundRect $borderInset $borderInset ($size - 2 * $borderInset) ($size - 2 * $borderInset) ([Math]::Max(2.0, $radius - $penWidth / 2.0))
        $graphics.DrawPath($pen, $borderPath)
        $pen.Dispose()
        $borderPath.Dispose()
    }

    $fontPixels = 118.0 * $scale
    if ($size -le 24) { $fontPixels = 130.0 * $scale }
    $letterBColor = if ($size -le 24) { [System.Drawing.Color]::FromArgb(255, 0x8a, 0xb8, 0xff) } else { $accent }
    $supersample = 4
    $scratch = New-Object System.Drawing.Bitmap(($size * $supersample), ($size * $supersample), ([System.Drawing.Imaging.PixelFormat]::Format32bppArgb))
    $scratchGraphics = [System.Drawing.Graphics]::FromImage($scratch)
    $scratchGraphics.SmoothingMode = [System.Drawing.Drawing2D.SmoothingMode]::AntiAlias
    $scratchGraphics.TextRenderingHint = [System.Drawing.Text.TextRenderingHint]::AntiAlias
    $scratchGraphics.Clear([System.Drawing.Color]::Transparent)
    $font = New-Object System.Drawing.Font('Segoe UI', ($fontPixels * $supersample), [System.Drawing.FontStyle]::Bold, [System.Drawing.GraphicsUnit]::Pixel)
    $format = [System.Drawing.StringFormat]::GenericTypographic
    $letterLSize = $scratchGraphics.MeasureString('L', $font, [System.Drawing.PointF]::Empty, $format)
    $padding = 2.0 * $supersample
    $letterLBrush = New-Object System.Drawing.SolidBrush($white)
    $letterBBrush = New-Object System.Drawing.SolidBrush($letterBColor)
    $scratchGraphics.DrawString('L', $font, $letterLBrush, $padding, $padding, $format)
    $scratchGraphics.DrawString('B', $font, $letterBBrush, ($padding + $letterLSize.Width), $padding, $format)
    $scratchGraphics.Dispose()

    $box = [CodexLbInkScan]::Box($scratch, 24)
    if ($box[2] -lt 0) { throw "Icon text rendered empty at size $size" }
    $inkCenterX = ($box[0] + $box[2] + 1) / 2.0
    $inkCenterY = ($box[1] + $box[3] + 1) / 2.0
    $offsetX = $size / 2.0 - $inkCenterX / $supersample
    $offsetY = $size / 2.0 - $inkCenterY / $supersample
    $graphics.InterpolationMode = [System.Drawing.Drawing2D.InterpolationMode]::HighQualityBicubic
    $graphics.PixelOffsetMode = [System.Drawing.Drawing2D.PixelOffsetMode]::HighQuality
    $destination = New-Object System.Drawing.RectangleF($offsetX, $offsetY, $size, $size)
    $graphics.DrawImage($scratch, $destination)

    $letterLBrush.Dispose(); $letterBBrush.Dispose(); $font.Dispose(); $scratch.Dispose()
    $brush.Dispose(); $path.Dispose(); $graphics.Dispose()

    $stream = New-Object System.IO.MemoryStream
    $bitmap.Save($stream, [System.Drawing.Imaging.ImageFormat]::Png)
    $entries += , @{ Size = $size; Data = $stream.ToArray() }
    $stream.Dispose(); $bitmap.Dispose()
}

$fileStream = [System.IO.File]::Create($out)
$writer = New-Object System.IO.BinaryWriter($fileStream)
$writer.Write([uint16]0)
$writer.Write([uint16]1)
$writer.Write([uint16]$entries.Count)
$offset = 6 + 16 * $entries.Count
foreach ($entry in $entries) {
    $byteSize = if ($entry.Size -ge 256) { 0 } else { $entry.Size }
    $writer.Write([byte]$byteSize)
    $writer.Write([byte]$byteSize)
    $writer.Write([byte]0)
    $writer.Write([byte]0)
    $writer.Write([uint16]1)
    $writer.Write([uint16]32)
    $writer.Write([uint32]$entry.Data.Length)
    $writer.Write([uint32]$offset)
    $offset += $entry.Data.Length
}
foreach ($entry in $entries) { $writer.Write($entry.Data) }
$writer.Close()
$fileStream.Close()

Write-Host "Wrote $out ($((Get-Item -LiteralPath $out).Length) bytes, $($entries.Count) sizes)"
