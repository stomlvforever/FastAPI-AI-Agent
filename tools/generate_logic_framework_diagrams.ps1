param(
    [string]$OutDir = "docs/diagrams"
)

$ErrorActionPreference = "Stop"

Add-Type -AssemblyName System.Drawing

function New-BlackPen {
    param(
        [System.Drawing.Color]$Color = [System.Drawing.Color]::Black,
        [float]$Width = 1.8,
        [bool]$Dashed = $false
    )
    $p = New-Object System.Drawing.Pen($Color, $Width)
    if ($Dashed) {
        $p.DashStyle = [System.Drawing.Drawing2D.DashStyle]::Dash
    }
    return $p
}

function Draw-Box {
    param(
        [System.Drawing.Graphics]$G,
        [string]$Text,
        [float]$X,
        [float]$Y,
        [float]$W,
        [float]$H,
        [System.Drawing.Font]$Font,
        [System.Drawing.Color]$BorderColor = [System.Drawing.Color]::Black,
        [System.Drawing.Color]$TextColor = [System.Drawing.Color]::Black,
        [System.Drawing.Color]$FillColor = [System.Drawing.Color]::Empty
)
    [float]$xx = [float](@($X)[0])
    [float]$yy = [float](@($Y)[0])
    [float]$ww = [float](@($W)[0])
    [float]$hh = [float](@($H)[0])

    if ($FillColor.A -gt 0) {
        $fillBrush = New-Object System.Drawing.SolidBrush($FillColor)
        $G.FillRectangle($fillBrush, $xx, $yy, $ww, $hh)
        $fillBrush.Dispose()
    }

    $pen = New-BlackPen -Color $BorderColor -Width 2
    $G.DrawRectangle($pen, $xx, $yy, $ww, $hh)
    $pen.Dispose()

    $rx = [float]($xx + 10)
    $ry = [float]($yy + 8)
    $rw = [float]($ww - 20)
    $rh = [float]($hh - 16)
    $rect = New-Object System.Drawing.RectangleF -ArgumentList $rx, $ry, $rw, $rh
    $fmt = New-Object System.Drawing.StringFormat
    $fmt.Alignment = [System.Drawing.StringAlignment]::Near
    $fmt.LineAlignment = [System.Drawing.StringAlignment]::Near
    $textBrush = New-Object System.Drawing.SolidBrush($TextColor)
    $G.DrawString($Text, $Font, $textBrush, $rect, $fmt)
    $textBrush.Dispose()
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
        [bool]$Dashed = $false,
        [System.Drawing.Color]$LineColor = [System.Drawing.Color]::Black,
        [System.Drawing.Color]$TextColor = [System.Drawing.Color]::Black
)
    [float]$sx = [float](@($X1)[0])
    [float]$sy = [float](@($Y1)[0])
    [float]$ex = [float](@($X2)[0])
    [float]$ey = [float](@($Y2)[0])

    $pen = New-BlackPen -Color $LineColor -Width 1.7 -Dashed:$Dashed
    $pen.EndCap = [System.Drawing.Drawing2D.LineCap]::ArrowAnchor
    $G.DrawLine($pen, $sx, $sy, $ex, $ey)

    if ($Label) {
        $mx = (($sx + $ex) / 2) + 4
        $my = (($sy + $ey) / 2) - 14
        $textBrush = New-Object System.Drawing.SolidBrush($TextColor)
        $G.DrawString($Label, $Font, $textBrush, $mx, $my)
        $textBrush.Dispose()
    }

    $pen.Dispose()
}

function Draw-Lifeline {
    param(
        [System.Drawing.Graphics]$G,
        [float]$X,
        [float]$TopY,
        [float]$BottomY,
        [float]$HeaderW,
        [float]$HeaderH,
        [string]$Label,
        [System.Drawing.Font]$Font,
        [System.Drawing.Color]$HeaderBorderColor = [System.Drawing.Color]::Black,
        [System.Drawing.Color]$HeaderTextColor = [System.Drawing.Color]::Black,
        [System.Drawing.Color]$HeaderFillColor = [System.Drawing.Color]::Empty,
        [System.Drawing.Color]$LifelineColor = [System.Drawing.Color]::Black
)
    [float]$lx = [float](@($X)[0])
    [float]$ty = [float](@($TopY)[0])
    [float]$by = [float](@($BottomY)[0])
    [float]$hw = [float](@($HeaderW)[0])
    [float]$hh = [float](@($HeaderH)[0])

    $hx = $lx - ($hw / 2)
    $hy = $ty
    Draw-Box -G $G -Text $Label -X $hx -Y $hy -W $hw -H $hh -Font $Font -BorderColor $HeaderBorderColor -TextColor $HeaderTextColor -FillColor $HeaderFillColor
    $pen = New-BlackPen -Color $LifelineColor -Width 1.2 -Dashed:$true
    $G.DrawLine($pen, $lx, $hy + $hh, $lx, $by)
    $pen.Dispose()
}

if (!(Test-Path $OutDir)) {
    New-Item -ItemType Directory -Path $OutDir -Force | Out-Null
}

# ---------------------------
# Part 1: Layered architecture
# ---------------------------
$w1 = 2200
$h1 = 1600
$bmp1 = New-Object System.Drawing.Bitmap $w1, $h1
$g1 = [System.Drawing.Graphics]::FromImage($bmp1)
$g1.SmoothingMode = [System.Drawing.Drawing2D.SmoothingMode]::AntiAlias
$g1.TextRenderingHint = [System.Drawing.Text.TextRenderingHint]::ClearTypeGridFit
$g1.Clear([System.Drawing.Color]::White)

$titleFont = New-Object System.Drawing.Font("Arial", 22, [System.Drawing.FontStyle]::Bold)
$subFont = New-Object System.Drawing.Font("Arial", 13, [System.Drawing.FontStyle]::Bold)
$codeFont = New-Object System.Drawing.Font("Consolas", 10, [System.Drawing.FontStyle]::Regular)
$tinyFont = New-Object System.Drawing.Font("Consolas", 9, [System.Drawing.FontStyle]::Regular)

$g1.DrawString(
    "FastAPI Code Logic Framework (Layered Architecture)",
    $titleFont,
    [System.Drawing.Brushes]::Black,
    40,
    20
)
$g1.DrawString(
    "White background, black lines. Dashed arrows indicate Depends(...) dependency injection.",
    $tinyFont,
    [System.Drawing.Brushes]::Black,
    40,
    65
)

$x = 80
$w = 2040
$layerH = 225

Draw-Box -G $g1 -Font $subFont -X $x -Y 110 -W $w -H $layerH -Text @"
Layer 1 - Route Layer
app/api/v1/routes/auth.py::login
app/api/v1/routes/items.py::create_item
app/api/v1/routes/items.py::list_items
app/api/v1/routes/items.py::get_item
app/api/v1/routes/items.py::update_item
app/api/v1/routes/items.py::delete_item
"@

Draw-Box -G $g1 -Font $subFont -X $x -Y 370 -W $w -H $layerH -Text @"
Layer 2 - Dependency Injection Layer
app/api/dependencies/db.py::get_db
app/api/dependencies/db.py::SessionDep (Depends(get_db))
app/api/dependencies/auth.py::get_current_user
app/api/dependencies/auth.py::CurrentUser (Depends(get_current_user))
fastapi.security::OAuth2PasswordBearer
"@

Draw-Box -G $g1 -Font $subFont -X $x -Y 630 -W $w -H $layerH -Text @"
Layer 3 - Service Layer
app/services/auth_service.py::authenticate_user
app/services/auth_service.py::create_token
app/services/item_service.py::create_item
app/services/item_service.py::list_items
app/services/item_service.py::get_item
app/services/item_service.py::update_item
app/services/item_service.py::delete_item
"@

Draw-Box -G $g1 -Font $subFont -X $x -Y 890 -W $w -H $layerH -Text @"
Layer 4 - Repository Layer
app/repositories/user_repo.py::get_by_email
app/repositories/item_repo.py::create
app/repositories/item_repo.py::list_by_owner
app/repositories/item_repo.py::get
app/repositories/item_repo.py::update
app/repositories/item_repo.py::delete
"@

Draw-Box -G $g1 -Font $subFont -X $x -Y 1150 -W $w -H $layerH -Text @"
Layer 5 - Security + Data Layer
app/core/security.py::verify_password
app/core/security.py::create_access_token
app/core/security.py::decode_token
app/db/models/user.py::User
app/db/models/item.py::Item
PostgreSQL::users/items
"@

Draw-Arrow -G $g1 -X1 1100 -Y1 335 -X2 1100 -Y2 366 -Label "route -> dependencies" -Font $tinyFont
Draw-Arrow -G $g1 -X1 1100 -Y1 595 -X2 1100 -Y2 626 -Label "dependencies -> services" -Font $tinyFont
Draw-Arrow -G $g1 -X1 1100 -Y1 855 -X2 1100 -Y2 886 -Label "services -> repositories" -Font $tinyFont
Draw-Arrow -G $g1 -X1 1100 -Y1 1115 -X2 1100 -Y2 1146 -Label "repositories -> db/security" -Font $tinyFont

$out1 = Join-Path $OutDir "fastapi_logic_framework_part1_layers.png"
$bmp1.Save($out1, [System.Drawing.Imaging.ImageFormat]::Png)

$g1.Dispose()
$bmp1.Dispose()

# ---------------------------
# Part 2: Call sequence diagram
# ---------------------------
$w2 = 3800
$h2 = 2300
$bmp2 = New-Object System.Drawing.Bitmap $w2, $h2
$g2 = [System.Drawing.Graphics]::FromImage($bmp2)
$g2.SmoothingMode = [System.Drawing.Drawing2D.SmoothingMode]::AntiAlias
$g2.TextRenderingHint = [System.Drawing.Text.TextRenderingHint]::ClearTypeGridFit
$g2.Clear([System.Drawing.Color]::White)

$titleFont2 = New-Object System.Drawing.Font("Microsoft YaHei UI", 34, [System.Drawing.FontStyle]::Bold)
$subFont2 = New-Object System.Drawing.Font("Microsoft YaHei UI", 20, [System.Drawing.FontStyle]::Bold)
$flowFont2 = New-Object System.Drawing.Font("Microsoft YaHei UI", 13, [System.Drawing.FontStyle]::Regular)
$miniFont2 = New-Object System.Drawing.Font("Microsoft YaHei UI", 12, [System.Drawing.FontStyle]::Regular)

$cInk = [System.Drawing.Color]::FromArgb(35, 35, 35)
$cBorder = [System.Drawing.Color]::FromArgb(60, 75, 90)
$cArrow = [System.Drawing.Color]::FromArgb(35, 76, 117)
$cDashed = [System.Drawing.Color]::FromArgb(90, 105, 120)
$cSectionFill = [System.Drawing.Color]::FromArgb(245, 249, 253)
$cHeaderFill = [System.Drawing.Color]::FromArgb(233, 242, 252)
$cDepFill = [System.Drawing.Color]::FromArgb(255, 247, 230)
$cSep = [System.Drawing.Color]::FromArgb(140, 155, 170)
$cTopBand = [System.Drawing.Color]::FromArgb(230, 240, 250)

$topBandBrush = New-Object System.Drawing.SolidBrush($cTopBand)
$g2.FillRectangle($topBandBrush, 0, 0, $w2, 110)
$topBandBrush.Dispose()

$inkBrush = New-Object System.Drawing.SolidBrush($cInk)
$g2.DrawString(
    "FastAPI 调用时序图（/auth/login 与 /items）",
    $titleFont2,
    $inkBrush,
    40,
    16
)
$g2.DrawString(
    "虚线箭头表示 Depends(...) 依赖注入；数据库调用标注 CRUD（SELECT/INSERT/UPDATE/DELETE）。",
    $flowFont2,
    $inkBrush,
    40,
    78
)

# Section A: /auth/login
Draw-Box -G $g2 -Font $subFont2 -X 40 -Y 130 -W 3720 -H 900 -Text "模块 A：/auth/login 调用链（自上而下）" -BorderColor $cBorder -TextColor $cInk -FillColor $cSectionFill

$authTop = 200
$authBottom = 995
$authHeaderW = 430
$authHeaderH = 104

$axClient = 260
$axRoute = 800
$axAuthSvc = 1340
$axUserRepo = 1880
$axDb = 2420
$axSec = 2960
$axToken = 3500

Draw-Lifeline -G $g2 -X $axClient -TopY $authTop -BottomY $authBottom -HeaderW 250 -HeaderH $authHeaderH -Label "客户端 Client" -Font $flowFont2 -HeaderBorderColor $cBorder -HeaderTextColor $cInk -HeaderFillColor $cHeaderFill -LifelineColor $cDashed
Draw-Lifeline -G $g2 -X $axRoute -TopY $authTop -BottomY $authBottom -HeaderW $authHeaderW -HeaderH $authHeaderH -Label "路由`napp/api/v1/routes/auth.py::login" -Font $flowFont2 -HeaderBorderColor $cBorder -HeaderTextColor $cInk -HeaderFillColor $cHeaderFill -LifelineColor $cDashed
Draw-Lifeline -G $g2 -X $axAuthSvc -TopY $authTop -BottomY $authBottom -HeaderW $authHeaderW -HeaderH $authHeaderH -Label "服务`napp/services/auth_service.py::authenticate_user" -Font $flowFont2 -HeaderBorderColor $cBorder -HeaderTextColor $cInk -HeaderFillColor $cHeaderFill -LifelineColor $cDashed
Draw-Lifeline -G $g2 -X $axUserRepo -TopY $authTop -BottomY $authBottom -HeaderW $authHeaderW -HeaderH $authHeaderH -Label "仓储`napp/repositories/user_repo.py::get_by_email" -Font $flowFont2 -HeaderBorderColor $cBorder -HeaderTextColor $cInk -HeaderFillColor $cHeaderFill -LifelineColor $cDashed
Draw-Lifeline -G $g2 -X $axDb -TopY $authTop -BottomY $authBottom -HeaderW 290 -HeaderH $authHeaderH -Label "数据库`nPostgreSQL::users" -Font $flowFont2 -HeaderBorderColor $cBorder -HeaderTextColor $cInk -HeaderFillColor $cHeaderFill -LifelineColor $cDashed
Draw-Lifeline -G $g2 -X $axSec -TopY $authTop -BottomY $authBottom -HeaderW $authHeaderW -HeaderH $authHeaderH -Label "安全校验`napp/core/security.py::verify_password" -Font $flowFont2 -HeaderBorderColor $cBorder -HeaderTextColor $cInk -HeaderFillColor $cHeaderFill -LifelineColor $cDashed
Draw-Lifeline -G $g2 -X $axToken -TopY $authTop -BottomY $authBottom -HeaderW $authHeaderW -HeaderH $authHeaderH -Label "Token 签发`napp/core/security.py::create_access_token" -Font $flowFont2 -HeaderBorderColor $cBorder -HeaderTextColor $cInk -HeaderFillColor $cHeaderFill -LifelineColor $cDashed

$depBox1X = 560
$depBox1Y = 390
Draw-Box -G $g2 -Font $miniFont2 -X $depBox1X -Y $depBox1Y -W 460 -H 96 -Text "依赖注入`napp/api/dependencies/db.py::SessionDep`nDepends(get_db)" -BorderColor $cBorder -TextColor $cInk -FillColor $cDepFill

Draw-Arrow -G $g2 -X1 $axClient -Y1 320 -X2 $axRoute -Y2 320 -Label "POST /api/v1/auth/login" -Font $flowFont2 -LineColor $cArrow -TextColor $cInk
Draw-Arrow -G $g2 -X1 $axRoute -Y1 415 -X2 ($depBox1X + 28) -Y2 ($depBox1Y + 38) -Label "Depends(...)" -Font $miniFont2 -Dashed:$true -LineColor $cDashed -TextColor $cInk
Draw-Arrow -G $g2 -X1 $axRoute -Y1 520 -X2 $axAuthSvc -Y2 520 -Label "app/services/auth_service.py::authenticate_user" -Font $miniFont2 -LineColor $cArrow -TextColor $cInk
Draw-Arrow -G $g2 -X1 $axAuthSvc -Y1 615 -X2 $axUserRepo -Y2 615 -Label "app/repositories/user_repo.py::get_by_email" -Font $miniFont2 -LineColor $cArrow -TextColor $cInk
Draw-Arrow -G $g2 -X1 $axUserRepo -Y1 705 -X2 $axDb -Y2 705 -Label "SELECT users（CRUD: SELECT）" -Font $miniFont2 -LineColor $cArrow -TextColor $cInk
Draw-Arrow -G $g2 -X1 $axAuthSvc -Y1 790 -X2 $axSec -Y2 790 -Label "app/core/security.py::verify_password" -Font $miniFont2 -LineColor $cArrow -TextColor $cInk
Draw-Arrow -G $g2 -X1 $axRoute -Y1 875 -X2 $axToken -Y2 875 -Label "app/services/auth_service.py::create_token -> app/core/security.py::create_access_token" -Font $miniFont2 -LineColor $cArrow -TextColor $cInk
Draw-Arrow -G $g2 -X1 $axRoute -Y1 955 -X2 $axClient -Y2 955 -Label "200 Token(access_token)" -Font $miniFont2 -LineColor $cArrow -TextColor $cInk

# Section B: /items
Draw-Box -G $g2 -Font $subFont2 -X 40 -Y 1060 -W 3720 -H 1210 -Text "模块 B：/items 调用链（自上而下，含 CRUD 分支）" -BorderColor $cBorder -TextColor $cInk -FillColor $cSectionFill

$itemsTop = 1130
$itemsBottom = 2235
$itemHeaderW = 440
$itemHeaderH = 104

$ixClient = 230
$ixRoute = 760
$ixCurrentUser = 1290
$ixUserRepo = 1820
$ixItemSvc = 2350
$ixItemRepo = 2880
$ixDb = 3410

Draw-Lifeline -G $g2 -X $ixClient -TopY $itemsTop -BottomY $itemsBottom -HeaderW 250 -HeaderH $itemHeaderH -Label "客户端 Client" -Font $flowFont2 -HeaderBorderColor $cBorder -HeaderTextColor $cInk -HeaderFillColor $cHeaderFill -LifelineColor $cDashed
Draw-Lifeline -G $g2 -X $ixRoute -TopY $itemsTop -BottomY $itemsBottom -HeaderW $itemHeaderW -HeaderH $itemHeaderH -Label "路由`napp/api/v1/routes/items.py::create_item/list_items/get_item/update_item/delete_item" -Font $flowFont2 -HeaderBorderColor $cBorder -HeaderTextColor $cInk -HeaderFillColor $cHeaderFill -LifelineColor $cDashed
Draw-Lifeline -G $g2 -X $ixCurrentUser -TopY $itemsTop -BottomY $itemsBottom -HeaderW $itemHeaderW -HeaderH $itemHeaderH -Label "认证依赖`napp/api/dependencies/auth.py::get_current_user" -Font $flowFont2 -HeaderBorderColor $cBorder -HeaderTextColor $cInk -HeaderFillColor $cHeaderFill -LifelineColor $cDashed
Draw-Lifeline -G $g2 -X $ixUserRepo -TopY $itemsTop -BottomY $itemsBottom -HeaderW $itemHeaderW -HeaderH $itemHeaderH -Label "用户仓储`napp/repositories/user_repo.py::get_by_email" -Font $flowFont2 -HeaderBorderColor $cBorder -HeaderTextColor $cInk -HeaderFillColor $cHeaderFill -LifelineColor $cDashed
Draw-Lifeline -G $g2 -X $ixItemSvc -TopY $itemsTop -BottomY $itemsBottom -HeaderW $itemHeaderW -HeaderH $itemHeaderH -Label "物品服务`napp/services/item_service.py::create_item/list_items/get_item/update_item/delete_item" -Font $flowFont2 -HeaderBorderColor $cBorder -HeaderTextColor $cInk -HeaderFillColor $cHeaderFill -LifelineColor $cDashed
Draw-Lifeline -G $g2 -X $ixItemRepo -TopY $itemsTop -BottomY $itemsBottom -HeaderW $itemHeaderW -HeaderH $itemHeaderH -Label "物品仓储`napp/repositories/item_repo.py::create/list_by_owner/get/update/delete" -Font $flowFont2 -HeaderBorderColor $cBorder -HeaderTextColor $cInk -HeaderFillColor $cHeaderFill -LifelineColor $cDashed
Draw-Lifeline -G $g2 -X $ixDb -TopY $itemsTop -BottomY $itemsBottom -HeaderW 310 -HeaderH $itemHeaderH -Label "数据库`nPostgreSQL::users/items" -Font $flowFont2 -HeaderBorderColor $cBorder -HeaderTextColor $cInk -HeaderFillColor $cHeaderFill -LifelineColor $cDashed

$depBox2X = 560
$depBox2Y = 1365
Draw-Box -G $g2 -Font $miniFont2 -X $depBox2X -Y $depBox2Y -W 440 -H 96 -Text "依赖注入`napp/api/dependencies/db.py::SessionDep`nDepends(get_db)" -BorderColor $cBorder -TextColor $cInk -FillColor $cDepFill

Draw-Arrow -G $g2 -X1 $ixClient -Y1 1285 -X2 $ixRoute -Y2 1285 -Label "POST/GET/PUT/DELETE /api/v1/items..." -Font $flowFont2 -LineColor $cArrow -TextColor $cInk
Draw-Arrow -G $g2 -X1 $ixRoute -Y1 1385 -X2 ($depBox2X + 28) -Y2 ($depBox2Y + 35) -Label "Depends(...)" -Font $miniFont2 -Dashed:$true -LineColor $cDashed -TextColor $cInk
Draw-Arrow -G $g2 -X1 $ixRoute -Y1 1460 -X2 $ixCurrentUser -Y2 1460 -Label "Depends(CurrentUser)" -Font $miniFont2 -Dashed:$true -LineColor $cDashed -TextColor $cInk
Draw-Arrow -G $g2 -X1 $ixCurrentUser -Y1 1540 -X2 $ixUserRepo -Y2 1540 -Label "app/repositories/user_repo.py::get_by_email" -Font $miniFont2 -LineColor $cArrow -TextColor $cInk
Draw-Arrow -G $g2 -X1 $ixUserRepo -Y1 1615 -X2 $ixDb -Y2 1615 -Label "SELECT users（CRUD: SELECT）" -Font $miniFont2 -LineColor $cArrow -TextColor $cInk

$penSep = New-BlackPen -Color $cSep -Width 1.2
$g2.DrawLine($penSep, 70, 1680, 3740, 1680)
$g2.DrawLine($penSep, 70, 1815, 3740, 1815)
$g2.DrawLine($penSep, 70, 1960, 3740, 1960)
$g2.DrawLine($penSep, 70, 2100, 3740, 2100)
$penSep.Dispose()

$g2.DrawString("POST 分支", $miniFont2, $inkBrush, 90, 1685)
Draw-Arrow -G $g2 -X1 $ixRoute -Y1 1730 -X2 $ixItemSvc -Y2 1730 -Label "app/services/item_service.py::create_item" -Font $miniFont2 -LineColor $cArrow -TextColor $cInk
Draw-Arrow -G $g2 -X1 $ixItemSvc -Y1 1765 -X2 $ixItemRepo -Y2 1765 -Label "app/repositories/item_repo.py::create" -Font $miniFont2 -LineColor $cArrow -TextColor $cInk
Draw-Arrow -G $g2 -X1 $ixItemRepo -Y1 1795 -X2 $ixDb -Y2 1795 -Label "INSERT items（CRUD: INSERT）" -Font $miniFont2 -LineColor $cArrow -TextColor $cInk

$g2.DrawString("GET 分支", $miniFont2, $inkBrush, 90, 1820)
Draw-Arrow -G $g2 -X1 $ixRoute -Y1 1860 -X2 $ixItemSvc -Y2 1860 -Label "app/services/item_service.py::list_items / get_item" -Font $miniFont2 -LineColor $cArrow -TextColor $cInk
Draw-Arrow -G $g2 -X1 $ixItemSvc -Y1 1890 -X2 $ixItemRepo -Y2 1890 -Label "app/repositories/item_repo.py::list_by_owner / get" -Font $miniFont2 -LineColor $cArrow -TextColor $cInk
Draw-Arrow -G $g2 -X1 $ixItemRepo -Y1 1925 -X2 $ixDb -Y2 1925 -Label "SELECT items（CRUD: SELECT）" -Font $miniFont2 -LineColor $cArrow -TextColor $cInk

$g2.DrawString("PUT 分支", $miniFont2, $inkBrush, 90, 1965)
Draw-Arrow -G $g2 -X1 $ixRoute -Y1 2005 -X2 $ixItemSvc -Y2 2005 -Label "app/services/item_service.py::update_item" -Font $miniFont2 -LineColor $cArrow -TextColor $cInk
Draw-Arrow -G $g2 -X1 $ixItemSvc -Y1 2035 -X2 $ixItemRepo -Y2 2035 -Label "app/repositories/item_repo.py::get + update" -Font $miniFont2 -LineColor $cArrow -TextColor $cInk
Draw-Arrow -G $g2 -X1 $ixItemRepo -Y1 2065 -X2 $ixDb -Y2 2065 -Label "SELECT + UPDATE items（CRUD: SELECT/UPDATE）" -Font $miniFont2 -LineColor $cArrow -TextColor $cInk

$g2.DrawString("DELETE 分支", $miniFont2, $inkBrush, 90, 2105)
Draw-Arrow -G $g2 -X1 $ixRoute -Y1 2145 -X2 $ixItemSvc -Y2 2145 -Label "app/services/item_service.py::delete_item" -Font $miniFont2 -LineColor $cArrow -TextColor $cInk
Draw-Arrow -G $g2 -X1 $ixItemSvc -Y1 2175 -X2 $ixItemRepo -Y2 2175 -Label "app/repositories/item_repo.py::get + delete" -Font $miniFont2 -LineColor $cArrow -TextColor $cInk
Draw-Arrow -G $g2 -X1 $ixItemRepo -Y1 2205 -X2 $ixDb -Y2 2205 -Label "SELECT + DELETE items（CRUD: SELECT/DELETE）" -Font $miniFont2 -LineColor $cArrow -TextColor $cInk

$out2 = Join-Path $OutDir "fastapi_logic_framework_part2_sequences.png"
$bmp2.Save($out2, [System.Drawing.Imaging.ImageFormat]::Png)

$inkBrush.Dispose()
$titleFont2.Dispose()
$subFont2.Dispose()
$flowFont2.Dispose()
$miniFont2.Dispose()

$g2.Dispose()
$bmp2.Dispose()

$titleFont.Dispose()
$subFont.Dispose()
$codeFont.Dispose()
$tinyFont.Dispose()

Write-Output "Generated: $out1"
Write-Output "Generated: $out2"
