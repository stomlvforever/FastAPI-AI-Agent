param(
    [string]$OutDir = "docs/diagrams"
)

$ErrorActionPreference = "Stop"
Add-Type -AssemblyName System.Drawing

function New-Pen {
    param(
        [System.Drawing.Color]$Color,
        [float]$Width = 1.5,
        [bool]$Dashed = $false
    )
    $p = New-Object System.Drawing.Pen($Color, $Width)
    if ($Dashed) {
        $p.DashStyle = [System.Drawing.Drawing2D.DashStyle]::Dash
    }
    return $p
}

function Draw-RectText {
    param(
        [System.Drawing.Graphics]$G,
        [float]$X,
        [float]$Y,
        [float]$W,
        [float]$H,
        [string]$Text,
        [System.Drawing.Font]$Font,
        [System.Drawing.Color]$BorderColor,
        [System.Drawing.Color]$FillColor,
        [System.Drawing.Color]$TextColor
)
    [float]$xx = [float](@($X)[0])
    [float]$yy = [float](@($Y)[0])
    [float]$ww = [float](@($W)[0])
    [float]$hh = [float](@($H)[0])

    $fill = New-Object System.Drawing.SolidBrush($FillColor)
    $G.FillRectangle($fill, $xx, $yy, $ww, $hh)
    $fill.Dispose()

    $pen = New-Pen -Color $BorderColor -Width 1.7
    $G.DrawRectangle($pen, $xx, $yy, $ww, $hh)
    $pen.Dispose()

    $rect = New-Object System.Drawing.RectangleF(($xx + 10), ($yy + 8), ($ww - 20), ($hh - 14))
    $fmt = New-Object System.Drawing.StringFormat
    $fmt.Alignment = [System.Drawing.StringAlignment]::Near
    $fmt.LineAlignment = [System.Drawing.StringAlignment]::Near
    $brush = New-Object System.Drawing.SolidBrush($TextColor)
    $G.DrawString($Text, $Font, $brush, $rect, $fmt)
    $brush.Dispose()
    $fmt.Dispose()
}

function Draw-Arrow {
    param(
        [System.Drawing.Graphics]$G,
        [float]$X1,
        [float]$Y1,
        [float]$X2,
        [float]$Y2,
        [string]$Label,
        [System.Drawing.Font]$Font,
        [System.Drawing.Color]$LineColor,
        [System.Drawing.Color]$TextColor,
        [bool]$Dashed = $false
)
    [float]$sx = [float](@($X1)[0])
    [float]$sy = [float](@($Y1)[0])
    [float]$ex = [float](@($X2)[0])
    [float]$ey = [float](@($Y2)[0])

    $pen = New-Pen -Color $LineColor -Width 1.6 -Dashed:$Dashed
    $pen.EndCap = [System.Drawing.Drawing2D.LineCap]::ArrowAnchor
    $G.DrawLine($pen, $sx, $sy, $ex, $ey)
    $pen.Dispose()

    if ($Label) {
        $mx = (($sx + $ex) / 2) + 4
        $my = (($sy + $ey) / 2) - 16
        $brush = New-Object System.Drawing.SolidBrush($TextColor)
        $G.DrawString($Label, $Font, $brush, $mx, $my)
        $brush.Dispose()
    }
}

function Draw-Lifeline {
    param(
        [System.Drawing.Graphics]$G,
        [float]$X,
        [float]$TopY,
        [float]$BottomY,
        [float]$HeadW,
        [float]$HeadH,
        [string]$Label,
        [System.Drawing.Font]$Font,
        [System.Drawing.Color]$BorderColor,
        [System.Drawing.Color]$FillColor,
        [System.Drawing.Color]$TextColor,
        [System.Drawing.Color]$LineColor
)
    [float]$lx = [float](@($X)[0])
    [float]$ty = [float](@($TopY)[0])
    [float]$by = [float](@($BottomY)[0])
    [float]$hw = [float](@($HeadW)[0])
    [float]$hh = [float](@($HeadH)[0])
    $hx = $lx - ($hw / 2)
    Draw-RectText -G $G -X $hx -Y $ty -W $hw -H $hh -Text $Label -Font $Font -BorderColor $BorderColor -FillColor $FillColor -TextColor $TextColor
    $pen = New-Pen -Color $LineColor -Width 1.1 -Dashed:$true
    $G.DrawLine($pen, $lx, $ty + $hh, $lx, $by)
    $pen.Dispose()
}

function Ensure-Dir {
    param([string]$Path)
    if (!(Test-Path $Path)) {
        New-Item -ItemType Directory -Path $Path -Force | Out-Null
    }
}

function Draw-AuthDiagram {
    param([string]$FilePath)

    $w = 3000
    $h = 1700
    $bmp = New-Object System.Drawing.Bitmap $w, $h
    $g = [System.Drawing.Graphics]::FromImage($bmp)
    $g.SmoothingMode = [System.Drawing.Drawing2D.SmoothingMode]::AntiAlias
    $g.TextRenderingHint = [System.Drawing.Text.TextRenderingHint]::ClearTypeGridFit
    $g.Clear([System.Drawing.Color]::White)

    $cText = [System.Drawing.Color]::FromArgb(32, 38, 46)
    $cBorder = [System.Drawing.Color]::FromArgb(90, 105, 120)
    $cHeader = [System.Drawing.Color]::FromArgb(236, 244, 252)
    $cNote = [System.Drawing.Color]::FromArgb(251, 247, 236)
    $cSection = [System.Drawing.Color]::FromArgb(245, 250, 255)
    $cArrow = [System.Drawing.Color]::FromArgb(36, 87, 148)
    $cDash = [System.Drawing.Color]::FromArgb(120, 130, 140)

    $titleFont = New-Object System.Drawing.Font("Microsoft YaHei UI", 30, [System.Drawing.FontStyle]::Bold)
    $subFont = New-Object System.Drawing.Font("Microsoft YaHei UI", 14, [System.Drawing.FontStyle]::Regular)
    $headFont = New-Object System.Drawing.Font("Microsoft YaHei UI", 12, [System.Drawing.FontStyle]::Regular)
    $msgFont = New-Object System.Drawing.Font("Microsoft YaHei UI", 11, [System.Drawing.FontStyle]::Regular)
    $noteTitleFont = New-Object System.Drawing.Font("Microsoft YaHei UI", 13, [System.Drawing.FontStyle]::Bold)
    $noteFont = New-Object System.Drawing.Font("Microsoft YaHei UI", 11, [System.Drawing.FontStyle]::Regular)

    $titleBrush = New-Object System.Drawing.SolidBrush($cText)
    $g.DrawString("标准时序图：/auth/login", $titleFont, $titleBrush, 40, 20)
    $g.DrawString("说明：虚线为 Depends(...) 依赖注入；数据库操作按 CRUD 标注。", $subFont, $titleBrush, 45, 85)

    Draw-RectText -G $g -X 30 -Y 130 -W 2940 -H 980 -Text "A. 认证登录流程（自上而下）" -Font $noteTitleFont -BorderColor $cBorder -FillColor $cSection -TextColor $cText

    $top = 190
    $bottom = 1080
    $headW = 420
    $headH = 94

    $x1 = 220
    $x2 = 760
    $x3 = 1300
    $x4 = 1840
    $x5 = 2380
    $x6 = 2820

    Draw-Lifeline -G $g -X $x1 -TopY $top -BottomY $bottom -HeadW 240 -HeadH $headH -Label "客户端`nClient" -Font $headFont -BorderColor $cBorder -FillColor $cHeader -TextColor $cText -LineColor $cDash
    Draw-Lifeline -G $g -X $x2 -TopY $top -BottomY $bottom -HeadW $headW -HeadH $headH -Label "路由`napp/api/v1/routes/auth.py::login" -Font $headFont -BorderColor $cBorder -FillColor $cHeader -TextColor $cText -LineColor $cDash
    Draw-Lifeline -G $g -X $x3 -TopY $top -BottomY $bottom -HeadW $headW -HeadH $headH -Label "服务`napp/services/auth_service.py::authenticate_user" -Font $headFont -BorderColor $cBorder -FillColor $cHeader -TextColor $cText -LineColor $cDash
    Draw-Lifeline -G $g -X $x4 -TopY $top -BottomY $bottom -HeadW $headW -HeadH $headH -Label "仓储`napp/repositories/user_repo.py::get_by_email" -Font $headFont -BorderColor $cBorder -FillColor $cHeader -TextColor $cText -LineColor $cDash
    Draw-Lifeline -G $g -X $x5 -TopY $top -BottomY $bottom -HeadW 310 -HeadH $headH -Label "数据库`nPostgreSQL::users" -Font $headFont -BorderColor $cBorder -FillColor $cHeader -TextColor $cText -LineColor $cDash
    Draw-Lifeline -G $g -X $x6 -TopY $top -BottomY $bottom -HeadW 350 -HeadH $headH -Label "安全`napp/core/security.py::verify_password" -Font $headFont -BorderColor $cBorder -FillColor $cHeader -TextColor $cText -LineColor $cDash

    Draw-RectText -G $g -X 560 -Y 360 -W 460 -H 92 -Text "依赖注入`napp/api/dependencies/db.py::SessionDep`nDepends(get_db)" -Font $msgFont -BorderColor $cBorder -FillColor $cNote -TextColor $cText

    Draw-Arrow -G $g -X1 $x1 -Y1 315 -X2 $x2 -Y2 315 -Label "1) POST /api/v1/auth/login" -Font $msgFont -LineColor $cArrow -TextColor $cText
    Draw-Arrow -G $g -X1 $x2 -Y1 395 -X2 590 -Y2 395 -Label "2) Depends(get_db)" -Font $msgFont -LineColor $cDash -TextColor $cText -Dashed:$true
    Draw-Arrow -G $g -X1 $x2 -Y1 500 -X2 $x3 -Y2 500 -Label "3) 调用 authenticate_user" -Font $msgFont -LineColor $cArrow -TextColor $cText
    Draw-Arrow -G $g -X1 $x3 -Y1 590 -X2 $x4 -Y2 590 -Label "4) get_by_email" -Font $msgFont -LineColor $cArrow -TextColor $cText
    Draw-Arrow -G $g -X1 $x4 -Y1 680 -X2 $x5 -Y2 680 -Label "5) SELECT users (CRUD: SELECT)" -Font $msgFont -LineColor $cArrow -TextColor $cText
    Draw-Arrow -G $g -X1 $x3 -Y1 770 -X2 $x6 -Y2 770 -Label "6) verify_password" -Font $msgFont -LineColor $cArrow -TextColor $cText
    Draw-Arrow -G $g -X1 $x2 -Y1 860 -X2 $x3 -Y2 860 -Label "7) create_token -> create_access_token" -Font $msgFont -LineColor $cArrow -TextColor $cText
    Draw-Arrow -G $g -X1 $x2 -Y1 950 -X2 $x1 -Y2 950 -Label "8) 200 Token(access_token)" -Font $msgFont -LineColor $cArrow -TextColor $cText

    Draw-RectText -G $g -X 30 -Y 1135 -W 2940 -H 525 -Text "函数注释（简版）" -Font $noteTitleFont -BorderColor $cBorder -FillColor $cSection -TextColor $cText

    $noteText = @"
- app/api/v1/routes/auth.py::login
  接收账号密码，组织认证流程，认证失败返回 401，成功返回 JWT。

- app/services/auth_service.py::authenticate_user
  通过邮箱查用户，调用密码校验逻辑，返回用户或 None。

- app/repositories/user_repo.py::get_by_email
  执行数据库查询，按 email 查 users 表（SELECT）。

- app/core/security.py::verify_password
  对明文密码和哈希密码进行校验。
"@
    $noteBrush = New-Object System.Drawing.SolidBrush($cText)
    $g.DrawString($noteText, $noteFont, $noteBrush, (New-Object System.Drawing.RectangleF(55, 1180, 2880, 455)))
    $noteBrush.Dispose()

    $titleBrush.Dispose()
    $titleFont.Dispose()
    $subFont.Dispose()
    $headFont.Dispose()
    $msgFont.Dispose()
    $noteTitleFont.Dispose()
    $noteFont.Dispose()

    $bmp.Save($FilePath, [System.Drawing.Imaging.ImageFormat]::Png)
    $g.Dispose()
    $bmp.Dispose()
}

function Draw-ItemsDiagram {
    param([string]$FilePath)

    $w = 3300
    $h = 2100
    $bmp = New-Object System.Drawing.Bitmap $w, $h
    $g = [System.Drawing.Graphics]::FromImage($bmp)
    $g.SmoothingMode = [System.Drawing.Drawing2D.SmoothingMode]::AntiAlias
    $g.TextRenderingHint = [System.Drawing.Text.TextRenderingHint]::ClearTypeGridFit
    $g.Clear([System.Drawing.Color]::White)

    $cText = [System.Drawing.Color]::FromArgb(32, 38, 46)
    $cBorder = [System.Drawing.Color]::FromArgb(90, 105, 120)
    $cHeader = [System.Drawing.Color]::FromArgb(236, 244, 252)
    $cNote = [System.Drawing.Color]::FromArgb(251, 247, 236)
    $cSection = [System.Drawing.Color]::FromArgb(245, 250, 255)
    $cArrow = [System.Drawing.Color]::FromArgb(36, 87, 148)
    $cDash = [System.Drawing.Color]::FromArgb(120, 130, 140)
    $cSep = [System.Drawing.Color]::FromArgb(155, 168, 181)

    $titleFont = New-Object System.Drawing.Font("Microsoft YaHei UI", 30, [System.Drawing.FontStyle]::Bold)
    $subFont = New-Object System.Drawing.Font("Microsoft YaHei UI", 14, [System.Drawing.FontStyle]::Regular)
    $headFont = New-Object System.Drawing.Font("Microsoft YaHei UI", 12, [System.Drawing.FontStyle]::Regular)
    $msgFont = New-Object System.Drawing.Font("Microsoft YaHei UI", 11, [System.Drawing.FontStyle]::Regular)
    $noteTitleFont = New-Object System.Drawing.Font("Microsoft YaHei UI", 13, [System.Drawing.FontStyle]::Bold)
    $noteFont = New-Object System.Drawing.Font("Microsoft YaHei UI", 11, [System.Drawing.FontStyle]::Regular)

    $titleBrush = New-Object System.Drawing.SolidBrush($cText)
    $g.DrawString("标准时序图：/items", $titleFont, $titleBrush, 40, 20)
    $g.DrawString("说明：先认证依赖，再进入 CRUD 分支。虚线表示 Depends(...)。", $subFont, $titleBrush, 45, 85)

    Draw-RectText -G $g -X 30 -Y 130 -W 3240 -H 1320 -Text "B. /items 调用链（自上而下，按 CRUD 分支）" -Font $noteTitleFont -BorderColor $cBorder -FillColor $cSection -TextColor $cText

    $top = 190
    $bottom = 1420
    $headW = 440
    $headH = 94

    $x1 = 210
    $x2 = 680
    $x3 = 1150
    $x4 = 1620
    $x5 = 2090
    $x6 = 2560
    $x7 = 3030

    Draw-Lifeline -G $g -X $x1 -TopY $top -BottomY $bottom -HeadW 240 -HeadH $headH -Label "客户端`nClient" -Font $headFont -BorderColor $cBorder -FillColor $cHeader -TextColor $cText -LineColor $cDash
    Draw-Lifeline -G $g -X $x2 -TopY $top -BottomY $bottom -HeadW $headW -HeadH $headH -Label "路由`napp/api/v1/routes/items.py::create_item/list_items/get_item/update_item/delete_item" -Font $headFont -BorderColor $cBorder -FillColor $cHeader -TextColor $cText -LineColor $cDash
    Draw-Lifeline -G $g -X $x3 -TopY $top -BottomY $bottom -HeadW $headW -HeadH $headH -Label "认证依赖`napp/api/dependencies/auth.py::get_current_user" -Font $headFont -BorderColor $cBorder -FillColor $cHeader -TextColor $cText -LineColor $cDash
    Draw-Lifeline -G $g -X $x4 -TopY $top -BottomY $bottom -HeadW $headW -HeadH $headH -Label "用户仓储`napp/repositories/user_repo.py::get_by_email" -Font $headFont -BorderColor $cBorder -FillColor $cHeader -TextColor $cText -LineColor $cDash
    Draw-Lifeline -G $g -X $x5 -TopY $top -BottomY $bottom -HeadW $headW -HeadH $headH -Label "物品服务`napp/services/item_service.py::create_item/list_items/get_item/update_item/delete_item" -Font $headFont -BorderColor $cBorder -FillColor $cHeader -TextColor $cText -LineColor $cDash
    Draw-Lifeline -G $g -X $x6 -TopY $top -BottomY $bottom -HeadW $headW -HeadH $headH -Label "物品仓储`napp/repositories/item_repo.py::create/list_by_owner/get/update/delete" -Font $headFont -BorderColor $cBorder -FillColor $cHeader -TextColor $cText -LineColor $cDash
    Draw-Lifeline -G $g -X $x7 -TopY $top -BottomY $bottom -HeadW 320 -HeadH $headH -Label "数据库`nPostgreSQL::users/items" -Font $headFont -BorderColor $cBorder -FillColor $cHeader -TextColor $cText -LineColor $cDash

    Draw-RectText -G $g -X 500 -Y 370 -W 420 -H 90 -Text "依赖注入`napp/api/dependencies/db.py::SessionDep`nDepends(get_db)" -Font $msgFont -BorderColor $cBorder -FillColor $cNote -TextColor $cText

    Draw-Arrow -G $g -X1 $x1 -Y1 320 -X2 $x2 -Y2 320 -Label "1) 请求 /api/v1/items*" -Font $msgFont -LineColor $cArrow -TextColor $cText
    Draw-Arrow -G $g -X1 $x2 -Y1 405 -X2 530 -Y2 405 -Label "2) Depends(get_db)" -Font $msgFont -LineColor $cDash -TextColor $cText -Dashed:$true
    Draw-Arrow -G $g -X1 $x2 -Y1 470 -X2 $x3 -Y2 470 -Label "3) Depends(CurrentUser)" -Font $msgFont -LineColor $cDash -TextColor $cText -Dashed:$true
    Draw-Arrow -G $g -X1 $x3 -Y1 555 -X2 $x4 -Y2 555 -Label "4) get_by_email" -Font $msgFont -LineColor $cArrow -TextColor $cText
    Draw-Arrow -G $g -X1 $x4 -Y1 640 -X2 $x7 -Y2 640 -Label "5) SELECT users (CRUD: SELECT)" -Font $msgFont -LineColor $cArrow -TextColor $cText

    $sepPen = New-Pen -Color $cSep -Width 1.0
    $g.DrawLine($sepPen, 60, 730, 3260, 730)
    $g.DrawLine($sepPen, 60, 870, 3260, 870)
    $g.DrawLine($sepPen, 60, 1010, 3260, 1010)
    $g.DrawLine($sepPen, 60, 1150, 3260, 1150)
    $sepPen.Dispose()

    $branchBrush = New-Object System.Drawing.SolidBrush($cText)
    $g.DrawString("POST 分支", $msgFont, $branchBrush, 70, 740)
    Draw-Arrow -G $g -X1 $x2 -Y1 790 -X2 $x5 -Y2 790 -Label "6) create_item" -Font $msgFont -LineColor $cArrow -TextColor $cText
    Draw-Arrow -G $g -X1 $x5 -Y1 820 -X2 $x6 -Y2 820 -Label "7) create" -Font $msgFont -LineColor $cArrow -TextColor $cText
    Draw-Arrow -G $g -X1 $x6 -Y1 850 -X2 $x7 -Y2 850 -Label "8) INSERT items (CRUD: INSERT)" -Font $msgFont -LineColor $cArrow -TextColor $cText

    $g.DrawString("GET 分支", $msgFont, $branchBrush, 70, 880)
    Draw-Arrow -G $g -X1 $x2 -Y1 930 -X2 $x5 -Y2 930 -Label "9) list_items/get_item" -Font $msgFont -LineColor $cArrow -TextColor $cText
    Draw-Arrow -G $g -X1 $x5 -Y1 960 -X2 $x6 -Y2 960 -Label "10) list_by_owner/get" -Font $msgFont -LineColor $cArrow -TextColor $cText
    Draw-Arrow -G $g -X1 $x6 -Y1 990 -X2 $x7 -Y2 990 -Label "11) SELECT items (CRUD: SELECT)" -Font $msgFont -LineColor $cArrow -TextColor $cText

    $g.DrawString("PUT 分支", $msgFont, $branchBrush, 70, 1020)
    Draw-Arrow -G $g -X1 $x2 -Y1 1070 -X2 $x5 -Y2 1070 -Label "12) update_item" -Font $msgFont -LineColor $cArrow -TextColor $cText
    Draw-Arrow -G $g -X1 $x5 -Y1 1100 -X2 $x6 -Y2 1100 -Label "13) get + update" -Font $msgFont -LineColor $cArrow -TextColor $cText
    Draw-Arrow -G $g -X1 $x6 -Y1 1130 -X2 $x7 -Y2 1130 -Label "14) SELECT + UPDATE (CRUD: SELECT/UPDATE)" -Font $msgFont -LineColor $cArrow -TextColor $cText

    $g.DrawString("DELETE 分支", $msgFont, $branchBrush, 70, 1160)
    Draw-Arrow -G $g -X1 $x2 -Y1 1210 -X2 $x5 -Y2 1210 -Label "15) delete_item" -Font $msgFont -LineColor $cArrow -TextColor $cText
    Draw-Arrow -G $g -X1 $x5 -Y1 1240 -X2 $x6 -Y2 1240 -Label "16) get + delete" -Font $msgFont -LineColor $cArrow -TextColor $cText
    Draw-Arrow -G $g -X1 $x6 -Y1 1270 -X2 $x7 -Y2 1270 -Label "17) SELECT + DELETE (CRUD: SELECT/DELETE)" -Font $msgFont -LineColor $cArrow -TextColor $cText

    $branchBrush.Dispose()

    Draw-RectText -G $g -X 30 -Y 1480 -W 3240 -H 590 -Text "函数注释（简版）" -Font $noteTitleFont -BorderColor $cBorder -FillColor $cSection -TextColor $cText

    $noteText = @"
- app/api/dependencies/auth.py::get_current_user
  从 Bearer Token 解码用户身份，确保请求者已登录。

- app/services/item_service.py::create_item
  组织创建逻辑，将 owner_id 与 payload 传给仓储层。

- app/services/item_service.py::list_items / get_item
  封装查询逻辑，支持分页、筛选、排序（最终在 repo 执行 SQL）。

- app/services/item_service.py::update_item
  先查存在性，再按字段更新，最后提交事务。

- app/services/item_service.py::delete_item
  先查存在性，再删除记录并提交事务。
"@
    $noteBrush = New-Object System.Drawing.SolidBrush($cText)
    $g.DrawString($noteText, $noteFont, $noteBrush, (New-Object System.Drawing.RectangleF(55, 1525, 3180, 520)))
    $noteBrush.Dispose()

    $titleBrush.Dispose()
    $titleFont.Dispose()
    $subFont.Dispose()
    $headFont.Dispose()
    $msgFont.Dispose()
    $noteTitleFont.Dispose()
    $noteFont.Dispose()

    $bmp.Save($FilePath, [System.Drawing.Imaging.ImageFormat]::Png)
    $g.Dispose()
    $bmp.Dispose()
}

function Compose-Combined {
    param(
        [string]$AuthPath,
        [string]$ItemsPath,
        [string]$OutPath
    )
    $img1 = [System.Drawing.Image]::FromFile($AuthPath)
    $img2 = [System.Drawing.Image]::FromFile($ItemsPath)

    $w = [Math]::Max($img1.Width, $img2.Width) + 80
    $h = $img1.Height + $img2.Height + 100
    $bmp = New-Object System.Drawing.Bitmap $w, $h
    $g = [System.Drawing.Graphics]::FromImage($bmp)
    $g.SmoothingMode = [System.Drawing.Drawing2D.SmoothingMode]::HighQuality
    $g.Clear([System.Drawing.Color]::White)

    $x1 = [int](($w - $img1.Width) / 2)
    $x2 = [int](($w - $img2.Width) / 2)
    $g.DrawImage($img1, $x1, 20, $img1.Width, $img1.Height)
    $g.DrawImage($img2, $x2, $img1.Height + 60, $img2.Width, $img2.Height)

    $bmp.Save($OutPath, [System.Drawing.Imaging.ImageFormat]::Png)
    $g.Dispose()
    $bmp.Dispose()
    $img1.Dispose()
    $img2.Dispose()
}

Ensure-Dir -Path $OutDir

$authStd = Join-Path $OutDir "fastapi_logic_framework_part2_auth_standard.png"
$itemsStd = Join-Path $OutDir "fastapi_logic_framework_part2_items_standard.png"
$combined = Join-Path $OutDir "fastapi_logic_framework_part2_sequences.png"

Draw-AuthDiagram -FilePath $authStd
Draw-ItemsDiagram -FilePath $itemsStd
Compose-Combined -AuthPath $authStd -ItemsPath $itemsStd -OutPath $combined

Write-Output "Generated: $authStd"
Write-Output "Generated: $itemsStd"
Write-Output "Generated: $combined"
