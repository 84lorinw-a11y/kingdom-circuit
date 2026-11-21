# Publication capacity

The complete published site and the files needed by one page are different measures. Adding another concert can increase the retained image library without increasing the images downloaded on an existing page.

The previous 149 MiB limit applied to every optimized WebP file combined. The November 20 approved image measurement was 155,537,314 bytes, leaving only 700,510 bytes below that limit. Routine additions could block the whole calendar even when individual images still met their requirements.

The default acceptance policy now measures every regular file in the publication artifact. This includes original photographs, retained archive artwork, optimized images, pages, data and the game. It warns at 750,000,000 bytes and blocks above 900,000,000 bytes. The warning leaves 150 MB for planned action, and the hard limit retains 100 MB of headroom below the published [GitHub Pages limit of 1 GB](https://docs.github.com/en/pages/getting-started-with-github-pages/github-pages-limits). These are decimal bytes. A capacity warning is not a failed publication.

The performance check records an early measurement. The final publication audit repeats the measurement after every writer and includes the publication manifest itself. Its JSON report and job summary state the measured bytes, file count, remaining capacity and warning status. If final capacity fails, no acceptance manifest remains for upload. Symbolic links and other nonregular files fail validation without following their targets. Hard links count separately by pathname because extraction can materialize separate copies.

Each optimized variant still has a 2 MiB maximum. Existing checks for responsive sizes, real image dimensions, local source coverage, loading priorities, missing resources and social image consistency remain. No original artwork, quality setting, crop or image encoding is changed by this policy. An explicitly supplied `--max-total-optimized-bytes` remains available as an additional library ceiling; it is no longer the default measure of page performance or hosting capacity.

When the warning threshold is reached, review the complete artifact report before changing anything. Preserve approved originals and archives. Moving retained media to a suitable asset host is a separate reviewed change, not an automatic deletion or quality reduction. Do not raise the hard limit to bypass the hosting constraint.
