function deleteConfirm(id) {
    const answer = confirm("Are you sure you want to delete this account ?");
    if (answer) {
        window.location.href = `/${id}/delete/`;
    }
}