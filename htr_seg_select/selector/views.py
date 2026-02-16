from django.shortcuts import render, redirect
from django.http import HttpResponse, HttpRequest
from django.conf import settings
from django.urls import reverse
import os
import shutil
import subprocess
import re

def document_segmenter(request: HttpRequest, doc_id: int):
    """
    Executes the external main.py segmenter script with the document file path as argument.
    Only opens GUI, does not wait for output.
    Reloads Document list page after execution, with GET state preserved.
    """
    from .models import Document

    try:
        document = Document.objects.get(pk=doc_id)
        doc_path = document.file.path
        # Prepare a clean environment for the subprocess, avoiding Django venv pollution
        segmenter_venv = "/mnt/5fb87de2-4e02-46a8-96a2-98df87017ed4/Projects/htr_segmenter/.venv"
        segmenter_python = f"{segmenter_venv}/bin/python"
        segmenter_env = os.environ.copy()
        # Remove variables that could interfere with Qt/venv
        for key in list(segmenter_env):
            if key.startswith("PYTHON") or key.startswith("QT_") or "cv2" in segmenter_env[key]:
                del segmenter_env[key]
        # Set PATH so segmenter venv comes first
        segmenter_env["PATH"] = f"{segmenter_venv}/bin:" + segmenter_env.get("PATH", "")
        subprocess.Popen(
            [segmenter_python,
             "/mnt/5fb87de2-4e02-46a8-96a2-98df87017ed4/Projects/htr_segmenter/main.py", doc_path],
            start_new_session=True,
            env=segmenter_env
        )
    except Exception as ex:
        # Could log error if needed, but per requirements, remain silent
        pass
    # Redirect to Django admin document changelist, preserving GET state
    base_url = reverse('admin:selector_document_changelist')
    query_str = request.GET.urlencode()
    if query_str:
        return redirect(f"{base_url}?{query_str}")
    else:
        return redirect(base_url)

def natural_key(s):
    return [int(text) if text.isdigit() else text.lower() for text in re.split(r'(\d+)', s)]

def segment_finalize_admin(request: HttpRequest, doc_id: int):
    from .models import Document, LineSegment
    doc = Document.objects.get(pk=doc_id)
    validated_folder = os.path.join(settings.MEDIA_ROOT, f"{doc.name}_validated")
    if doc and os.path.isdir(validated_folder):
        for fname in os.listdir(validated_folder):
            fpath = os.path.join(validated_folder, fname)
            if os.path.isfile(fpath):
                try:
                    order = int(os.path.splitext(fname)[0])
                except ValueError:
                    continue
                # Create LineSegment referencing the file
                LineSegment.objects.create(
                    file=f"{doc.name}_validated/{fname}",
                    order=order,
                    document=doc
                )
    # Redirect to admin changelist, including any filter/query params
    from django.urls import reverse
    base_url = reverse("admin:selector_document_changelist")
    # Build query params from request.GET
    query_str = request.GET.urlencode()
    if query_str:
        return redirect(f"{base_url}?{query_str}")
    else:
        return redirect(base_url)

def segment_finalize(request: HttpRequest, doc_name: str, page_name: str):
    if request.method == "POST":
        from .models import Document, LineSegment
        import os
        validated_folder = os.path.join(settings.MEDIA_ROOT, f"{doc_name}_{page_name}_validated")
        doc = Document.objects.filter(name=f"{doc_name}_{page_name}").first()
        if doc and os.path.isdir(validated_folder):
            for fname in os.listdir(validated_folder):
                fpath = os.path.join(validated_folder, fname)
                if os.path.isfile(fpath):
                    try:
                        order = int(os.path.splitext(fname)[0])
                    except ValueError:
                        continue
                    # Create LineSegment referencing the file
                    LineSegment.objects.create(
                        file=f"{doc_name}_{page_name}_validated/{fname}",
                        order=order,
                        document=doc
                    )
        # Redirect back to compare page
        model1 = request.GET.get("model1", "blla")
        model2 = request.GET.get("model2", "muharaf")
        idx1 = request.GET.get("idx1", "0")
        idx2 = request.GET.get("idx2", "0")
        return redirect(f"/compare/{doc_name}/{page_name}?model1={model1}&model2={model2}&idx1={idx1}&idx2={idx2}")

def segment_recreate(request: HttpRequest, doc_name: str, page_name: str):
    if request.method == "POST":
        from . import admin as seg_admin
        model1 = request.GET.get("model1", "blla")
        model2 = request.GET.get("model2", "muharaf")
        recreate = request.POST.get("recreate")
        padding = int(request.POST.get("padding", 10))
        page_img_path = None
        for ext in [".jpg", ".jpeg", ".png"]:
            candidate = os.path.join(settings.MEDIA_ROOT, f"{doc_name}_{page_name}{ext}")
            if os.path.exists(candidate):
                page_img_path = candidate
                break
        if recreate == "model1":
            model_func = getattr(seg_admin, f"extract_lines_{model1}", None)
            if model_func and page_img_path:
                model_file = f"{model1}_seg_best.mlmodel" if model1 == "muharaf" else "blla.mlmodel"
                from kraken.lib import vgsl
                model_obj = vgsl.TorchVGSLModel.load_model(model_file)
                model_func(page_img_path, model1, f"{doc_name}_{page_name}", model_obj, padding=padding)
        elif recreate == "model2":
            model_func = getattr(seg_admin, f"extract_lines_{model2}", None)
            if model_func and page_img_path:
                model_file = f"{model2}_seg_best.mlmodel" if model2 == "muharaf" else "blla.mlmodel"
                from kraken.lib import vgsl
                model_obj = vgsl.TorchVGSLModel.load_model(model_file)
                model_func(page_img_path, model2, f"{doc_name}_{page_name}", model_obj, padding=padding)
        # After recreation, redirect to segment_compare with preserved idx1 and idx2
        idx1 = request.GET.get("idx1", "0")
        idx2 = request.GET.get("idx2", "0")
        return redirect(f"/compare/{doc_name}/{page_name}?model1={model1}&model2={model2}&idx1={idx1}&idx2={idx2}")

def segment_compare(request: HttpRequest, doc_name: str, page_name: str):
    # Model folder names
    model1 = request.GET.get("model1", "blla")
    model2 = request.GET.get("model2", "muharaf")
    idx1 = int(request.GET.get("idx1", 0))
    idx2 = int(request.GET.get("idx2", 0))
    padding = 10

    folder1 = f"{doc_name}_{page_name}_{model1}"
    folder2 = f"{doc_name}_{page_name}_{model2}"
    media_root = settings.MEDIA_ROOT

    folder1_path = os.path.join(media_root, folder1)
    folder2_path = os.path.join(media_root, folder2)

    # List segmentation files for each model (natural sort)
    segs1 = sorted([f for f in os.listdir(folder1_path) if os.path.isfile(os.path.join(folder1_path, f))], key=natural_key)
    segs2 = sorted([f for f in os.listdir(folder2_path) if os.path.isfile(os.path.join(folder2_path, f))], key=natural_key)

    # Clamp indices
    idx1 = max(0, min(idx1, len(segs1) - 1)) if segs1 else 0
    idx2 = max(0, min(idx2, len(segs2) - 1)) if segs2 else 0

    # Accept logic
    accept1 = request.GET.get("accept1")
    accept2 = request.GET.get("accept2")
    validated_folder = f"{doc_name}_{page_name}_validated"
    validated_path = os.path.join(media_root, validated_folder)
    os.makedirs(validated_path, exist_ok=True)

    if accept1 and segs1:
        src = os.path.join(folder1_path, segs1[idx1])
        dst = os.path.join(validated_path, f"{len(os.listdir(validated_path)) + 1}{os.path.splitext(segs1[idx1])[1]}")
        shutil.copy2(src, dst)
        next_idx1 = min(idx1 + 1, len(segs1) - 1)
        next_idx2 = min(idx2 + 1, len(segs2) - 1)
        return redirect(request.path + f"?model1={model1}&model2={model2}&idx1={next_idx1}&idx2={next_idx2}")

    if accept2 and segs2:
        src = os.path.join(folder2_path, segs2[idx2])
        dst = os.path.join(validated_path, f"{len(os.listdir(validated_path)) + 1}{os.path.splitext(segs2[idx2])[1]}")
        shutil.copy2(src, dst)
        next_idx1 = min(idx1 + 1, len(segs1) - 1)
        next_idx2 = min(idx2 + 1, len(segs2) - 1)
        return redirect(request.path + f"?model1={model1}&model2={model2}&idx1={next_idx1}&idx2={next_idx2}")

    # Full page image (assume in media_root as {doc_name}_{page_name}.jpg or .png)
    page_img = None
    for ext in [".jpg", ".jpeg", ".png"]:
        candidate = os.path.join(media_root, f"{doc_name}_{page_name}{ext}")
        if os.path.exists(candidate):
            page_img = settings.MEDIA_URL + os.path.basename(candidate)
            break

    context = {
        "model1": model1,
        "model2": model2,
        "idx1": idx1,
        "idx2": idx2,
        "seg1": settings.MEDIA_URL + folder1 + "/" + segs1[idx1] if segs1 else None,
        "seg2": settings.MEDIA_URL + folder2 + "/" + segs2[idx2] if segs2 else None,
        "seg1_count": len(segs1),
        "seg2_count": len(segs2),
        "page_img": page_img,
        "doc_name": doc_name,
        "page_name": page_name,
    }
    return render(request, "selector/segment_compare.html", context)

def segment_list(request: HttpRequest):
    relative_path = "my_parent_folder"  # change this
    base_dir = os.path.join(settings.MEDIA_ROOT, relative_path)
    try:
        folder_names = [
            name
            for name in os.listdir(base_dir)
            if os.path.isdir(os.path.join(base_dir, name))
        ]
    except (FileNotFoundError, NotADirectoryError):
        folder_names = []
    return render(request, "selector/segment_list.html", {"folder_names": folder_names})

def pdf2image(request: HttpRequest):
    return render(request, "selector/pdf2image.html", {})