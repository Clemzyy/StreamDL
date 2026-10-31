# PayPal icon source

Official vector mark: https://www.paypalobjects.com/paypal-ui/logos/svg/paypal-mark-color.svg

The standalone SVG is preserved here so the small toolbar icon can be rendered
directly from vector curves, without a white matte, outline or shadow.

Render with Inkscape:

```powershell
inkscape assets/paypal-mark-color.svg --export-type=png --export-filename=social_paypal.png --export-width=32 --export-height=32 --export-background-opacity=0
Copy-Item -LiteralPath social_paypal.png -Destination social_paypal_dark.png
```

Both themes use this same transparent, full-color mark.
